from __future__ import annotations

import json
import re
import string
import time
import unicodedata
from concurrent.futures import ThreadPoolExecutor
from dataclasses import dataclass
from typing import Any, Callable, Iterator
from uuid import uuid4

from ianest_core.adapters import Event, ModelAdapter
from ianest_core.config.schema import CoreConfig, OrchestrationTargetConfig
from ianest_core.errors import CoreError
from ianest_core.identity import Identity
from ianest_core.registry import AvailabilityProvider
from ianest_core.runtime.prompt_runtime import PromptRunResult, PromptRuntime
from ianest_core.telemetry import TelemetryWriter

AdapterFactory = Callable[[str], ModelAdapter | None]


@dataclass(frozen=True)
class TaskResult:
    response: str
    stop_reason: str
    subtasks: list[dict[str, Any]]
    params: dict[str, Any]
    trace: dict[str, Any]
    checkpoints: list[str]

    def to_dict(self) -> dict[str, Any]:
        return {
            "response": self.response,
            "stop_reason": self.stop_reason,
            "subtasks": self.subtasks,
            "params": self.params,
            "trace": self.trace,
            "checkpoints": self.checkpoints,
        }


class TaskRuntime:
    def __init__(
        self,
        config: CoreConfig,
        telemetry: TelemetryWriter | None = None,
        availability: AvailabilityProvider | None = None,
        adapter_factory: AdapterFactory | None = None,
        simulated: dict[str, Any] | None = None,
    ) -> None:
        if config.orchestration is None:
            raise CoreError(
                "ConfigError",
                "task.run requires the optional orchestration configuration section",
                "orchestration",
            )
        self.config = config
        self.settings = config.orchestration
        self.adapter_factory = adapter_factory
        self.prompt_runtime = PromptRuntime(
            config,
            telemetry=telemetry,
            availability=availability,
            adapter_factory=(lambda model: adapter_factory(model.id)) if adapter_factory else None,
        )
        self.simulated = simulated or {}

    def run(self, *, prompt: str, identity_override: dict[str, str] | None = None, request_id: str | None = None) -> TaskResult:
        events = list(self.stream(prompt=prompt, identity_override=identity_override, request_id=request_id))
        done = next(event for event in reversed(events) if event.type == "task_done")
        return TaskResult(**done.data)

    def stream(
        self,
        *,
        prompt: str,
        identity_override: dict[str, str] | None = None,
        request_id: str | None = None,
    ) -> Iterator[Event]:
        started = time.monotonic()
        parent_request_id = request_id or str(uuid4())
        task_id = str(uuid4())
        identity_data = dict(identity_override or {})
        identity = Identity.from_defaults(self.config.identity_defaults, identity_data)
        checkpoints: list[str] = []
        subtasks: list[dict[str, Any]] = []
        response = ""
        iterations = 0
        replans = 0

        yield self._checkpoint("task_received", checkpoints, identity, parent_request_id, task_id, {"prompt": prompt})
        plan = self._plan(prompt, identity_data, parent_request_id, task_id)

        while True:
            yield self._checkpoint("plan_ready", checkpoints, identity, parent_request_id, task_id, {"plan": plan})
            if len(plan) > self.settings.max_subtasks:
                stop_reason = "max_subtasks"
                break

            iterations += 1
            iteration_results = self._fan_out(plan, identity_data, parent_request_id, task_id)
            subtasks.extend(iteration_results)
            for item in iteration_results:
                yield self._checkpoint("subtask_done", checkpoints, identity, parent_request_id, task_id, item)

            response = self._combine(prompt, iteration_results, identity_data, parent_request_id, task_id)
            yield self._checkpoint("combine_ready", checkpoints, identity, parent_request_id, task_id, {"response": response})
            decision = self._evaluate(prompt, response, identity_data, parent_request_id, task_id)
            yield self._checkpoint(
                "iteration_end", checkpoints, identity, parent_request_id, task_id,
                {"iteration": iterations, "decision": decision},
            )

            stop_reason = self._limit_reason(started)
            if stop_reason:
                break
            if decision == "done":
                stop_reason = "task_done"
                break
            if decision == "replan":
                if replans >= self.settings.max_replans:
                    stop_reason = "max_replans"
                    break
                replans += 1
                plan = self._plan(prompt, identity_data, parent_request_id, task_id)
                continue
            if iterations >= self.settings.max_iterations:
                stop_reason = "max_iterations"
                break

        payload = {
            "response": response,
            "stop_reason": stop_reason,
            "subtasks": subtasks,
            "params": self._params(),
            "trace": {
                "request_id": parent_request_id,
                "task_id": task_id,
                "capability": "task.run",
                **identity.to_dict(),
                "latency_ms": int((time.monotonic() - started) * 1000),
                "stop_reason": stop_reason,
            },
            "checkpoints": [*checkpoints, "task_done"],
        }
        yield self._checkpoint("task_done", checkpoints, identity, parent_request_id, task_id, payload)

    def _plan(self, prompt: str, identity: dict[str, str], parent: str, task_id: str) -> list[dict[str, Any]]:
        domain_ids = ", ".join(domain.id for domain in self.config.domains)
        instruction = (
            "Decompose the task. Return only a JSON list of objects with prompt and optional "
            "domain_hint and depends_on. If domain_hint is used, it must be one of: "
            f"{domain_ids}. Task: {prompt}"
        )
        result = self._run_target(self.settings.planner, instruction, identity, parent, task_id, "planner")
        plan = _parse_plan(result.response)
        if not isinstance(plan, list) or not all(self._valid_subtask(item) for item in plan):
            raise CoreError("PlanParseError", "planner returned an invalid plan", "plan")
        return [dict(item) for item in plan]

    def _fan_out(self, plan: list[dict[str, Any]], identity: dict[str, str], parent: str, task_id: str) -> list[dict[str, Any]]:
        pending = set(range(len(plan)))
        completed: dict[int, dict[str, Any]] = {}
        while pending:
            ready = [index for index in sorted(pending) if self._dependencies(plan[index]).issubset(completed)]
            if not ready:
                raise CoreError("PlanDependencyError", "plan contains cyclic or invalid dependencies", "depends_on")
            with ThreadPoolExecutor(max_workers=self.settings.max_parallel) as executor:
                futures = {index: executor.submit(self._run_subtask, index, plan[index], identity, parent, task_id) for index in ready}
                for index in ready:
                    completed[index] = futures[index].result()
                    pending.remove(index)
        return [completed[index] for index in range(len(plan))]

    def _run_subtask(self, index: int, item: dict[str, Any], identity: dict[str, str], parent: str, task_id: str) -> dict[str, Any]:
        domain_hint = item.get("domain_hint")
        domain_id = self._resolve_domain_hint(domain_hint)
        ignored_hint = domain_hint if domain_hint and domain_id is None else None
        request_id = str(uuid4())
        trace_payload = {"task_id": task_id, "parent_request_id": parent, "subtask_index": index}
        if ignored_hint is not None:
            trace_payload["domain_hint_ignored"] = ignored_hint
        result = self._run_prompt(
            prompt=str(item["prompt"]), domain_id=domain_id,
            identity=identity, request_id=request_id, trace_payload=trace_payload,
        )
        record = {
            "index": index,
            "prompt": item["prompt"],
            "response": result.response,
            "domain": result.domain,
            "model": result.model,
            "finish_reason": result.trace.get("finish_reason"),
            "substituted": bool(result.trace.get("substituted")),
            "request_id": request_id,
            "task_id": task_id,
            "parent_request_id": parent,
        }
        if ignored_hint is not None:
            record["domain_hint_ignored"] = ignored_hint
        return record

    def _resolve_domain_hint(self, value: Any) -> str | None:
        if not isinstance(value, str) or not value.strip():
            return None
        normalized = _normalize_domain_hint(value)
        for domain in self.config.domains:
            if _normalize_domain_hint(domain.id) == normalized:
                return domain.id
        return None

    def _combine(self, prompt: str, results: list[dict[str, Any]], identity: dict[str, str], parent: str, task_id: str) -> str:
        content = f"Combine the subtask results into one answer. Task: {prompt}\nResults: {json.dumps(results, ensure_ascii=False)}"
        return self._run_target(self.settings.combiner, content, identity, parent, task_id, "combiner").response

    def _evaluate(self, prompt: str, response: str, identity: dict[str, str], parent: str, task_id: str) -> str:
        content = (
            "Evaluate the combined answer. Return only one word: done, rerun, or replan. "
            f"Task: {prompt}\nAnswer: {response}"
        )
        response_text = self._run_target(
            self.settings.planner, content, identity, parent, task_id, "evaluator"
        ).response
        return _parse_evaluation_decision(response_text)

    def _run_target(self, target: OrchestrationTargetConfig, prompt: str, identity: dict[str, str], parent: str, task_id: str, role: str) -> PromptRunResult:
        return self._run_prompt(
            prompt=prompt, model_id=target.model, domain_id=target.domain, profile_id=target.profile,
            identity=identity, request_id=str(uuid4()),
            trace_payload={"task_id": task_id, "parent_request_id": parent, "orchestration_role": role},
        )

    def _run_prompt(self, **kwargs: Any) -> PromptRunResult:
        return self.prompt_runtime.run(
            prompt=kwargs["prompt"], model_id=kwargs.get("model_id"), domain_id=kwargs.get("domain_id"),
            profile_id=kwargs.get("profile_id"), identity_override=kwargs["identity"],
            request_id=kwargs["request_id"], trace_payload=kwargs["trace_payload"],
        )

    def _checkpoint(self, name: str, checkpoints: list[str], identity: Identity, parent: str, task_id: str, data: dict[str, Any]) -> Event:
        checkpoints.append(name)
        payload = {"task_id": task_id, "parent_request_id": parent, **data}
        self.prompt_runtime.telemetry.record(
            request_id=parent, event=name, capability="task.run", identity=identity, payload=payload,
        )
        return Event(name, data)

    def _limit_reason(self, started: float) -> str | None:
        elapsed = float(self.simulated.get("elapsed_s", time.monotonic() - started))
        context = int(self.simulated.get("context_tokens", 0))
        if elapsed >= self.settings.max_time_s:
            return "max_time"
        if context >= self.settings.max_context_tokens:
            return "max_context_tokens"
        return None

    def _params(self) -> dict[str, Any]:
        return {name: getattr(self.settings, name) for name in (
            "max_subtasks", "max_iterations", "max_replans", "max_time_s", "max_context_tokens", "max_parallel"
        )}

    @staticmethod
    def _valid_subtask(item: Any) -> bool:
        return isinstance(item, dict) and isinstance(item.get("prompt"), str) and bool(item["prompt"])

    @staticmethod
    def _dependencies(item: dict[str, Any]) -> set[int]:
        value = item.get("depends_on", [])
        if isinstance(value, int):
            return {value}
        if isinstance(value, list) and all(isinstance(index, int) for index in value):
            return set(value)
        if value in (None, []):
            return set()
        raise CoreError("PlanDependencyError", "depends_on must contain subtask indexes", "depends_on")


def _parse_plan(text: str) -> Any:
    without_fences = re.sub(r"```(?:json)?\s*", "", text, flags=re.IGNORECASE)
    without_fences = without_fences.replace("```", "").strip()
    try:
        return json.loads(without_fences)
    except json.JSONDecodeError as first_error:
        start = without_fences.find("[")
        if start < 0:
            raise CoreError("PlanParseError", "planner returned invalid JSON", "plan") from first_error
        try:
            value, _ = json.JSONDecoder().raw_decode(without_fences[start:])
            return value
        except json.JSONDecodeError as exc:
            raise CoreError("PlanParseError", "planner returned invalid JSON", "plan") from exc


def _normalize_domain_hint(value: str) -> str:
    decomposed = unicodedata.normalize("NFKD", value.strip().lower())
    return "".join(character for character in decomposed if not unicodedata.combining(character))


def _parse_evaluation_decision(text: str) -> str:
    normalized = text.lower().strip().strip(string.whitespace + string.punctuation)
    decisions = {"done", "rerun", "replan"}
    if normalized in decisions:
        return normalized
    matches = re.findall(r"\b(?:done|rerun|replan)\b", text.lower())
    unique = set(matches)
    if len(unique) == 1:
        return unique.pop()
    raise CoreError("EvaluationDecisionError", "evaluator returned an invalid decision", "decision")
