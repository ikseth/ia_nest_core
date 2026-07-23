from __future__ import annotations

import json
import re
import string
import time
import unicodedata
from concurrent.futures import ThreadPoolExecutor
from dataclasses import dataclass, field
from threading import Lock
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
    mode: str | None = None
    coverage: dict[str, Any] | None = None
    chunks: list[dict[str, Any]] | None = None

    def to_dict(self) -> dict[str, Any]:
        result = {
            "response": self.response,
            "stop_reason": self.stop_reason,
            "subtasks": self.subtasks,
            "params": self.params,
            "trace": self.trace,
            "checkpoints": self.checkpoints,
        }
        if self.mode is not None:
            result["mode"] = self.mode
        if self.coverage is not None:
            result["coverage"] = self.coverage
        if self.chunks is not None:
            result["chunks"] = self.chunks
        return result


@dataclass
class _TokenUsage:
    tokens_in: int = 0
    tokens_out: int = 0
    lock: Lock = field(default_factory=Lock)

    def add(self, result: PromptRunResult) -> None:
        with self.lock:
            self.tokens_in += int(result.trace.get("tokens_in", 0) or 0)
            self.tokens_out += int(result.trace.get("tokens_out", 0) or 0)

    def snapshot(self) -> tuple[int, int]:
        with self.lock:
            return self.tokens_in, self.tokens_out

    def total(self) -> int:
        tokens_in, tokens_out = self.snapshot()
        return tokens_in + tokens_out


@dataclass
class _CoverageUnit:
    id: str
    prompt: str
    depends_on: list[str]
    domain_hint: str | None = None
    domain_hint_ignored: str | None = None
    domain: str = ""
    model: str = ""
    retries: int = 0
    state: str = "pending"
    fragment: dict[str, Any] | None = None


@dataclass
class _CoverageLedger:
    units: list[_CoverageUnit]
    token_usage: _TokenUsage
    chunks: list[dict[str, Any]] = field(default_factory=list)
    chunk_index: int = 0
    no_progress_iterations: int = 0
    emitted_chunk_indexes: set[int] = field(default_factory=set)

    def completed_ids(self) -> list[str]:
        return [unit.id for unit in self.units if unit.state == "completed"]

    def failed_ids(self) -> list[str]:
        return [unit.id for unit in self.units if unit.state == "failed"]

    def pending_ids(self) -> list[str]:
        return [unit.id for unit in self.units if unit.state == "pending"]


@dataclass(frozen=True)
class _CoverageGroup:
    chunk_index: int
    units: list[_CoverageUnit]
    domain: str
    model: str
    completed_ids: list[str]


@dataclass(frozen=True)
class _CoverageGeneration:
    group: _CoverageGroup
    request_id: str
    result: PromptRunResult | None
    error: CoreError | None = None


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

    def run(
        self,
        *,
        prompt: str,
        identity_override: dict[str, str] | None = None,
        request_id: str | None = None,
        mode: str = "pipeline",
    ) -> TaskResult:
        events = list(
            self.stream(
                prompt=prompt,
                identity_override=identity_override,
                request_id=request_id,
                mode=mode,
            )
        )
        done = next(event for event in reversed(events) if event.type == "task_done")
        return TaskResult(**done.data)

    def stream(
        self,
        *,
        prompt: str,
        identity_override: dict[str, str] | None = None,
        request_id: str | None = None,
        mode: str = "pipeline",
    ) -> Iterator[Event]:
        if mode not in {"pipeline", "coverage"}:
            raise CoreError("ConfigError", "task.run mode must be pipeline or coverage", "mode")
        if mode == "coverage":
            if self.settings.coverage is None:
                raise CoreError(
                    "ConfigError",
                    "coverage mode requires orchestration.coverage configuration",
                    "orchestration.coverage",
                )
            yield from self._stream_coverage(
                prompt=prompt,
                identity_override=identity_override,
                request_id=request_id,
            )
            return

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
        token_usage = _TokenUsage()

        yield self._checkpoint("task_received", checkpoints, identity, parent_request_id, task_id, {"prompt": prompt})
        plan = self._plan(prompt, identity_data, parent_request_id, task_id, token_usage)

        while True:
            yield self._checkpoint("plan_ready", checkpoints, identity, parent_request_id, task_id, {"plan": plan})
            if len(plan) > self.settings.max_subtasks:
                stop_reason = "max_subtasks"
                break

            iterations += 1
            iteration_results = self._fan_out(plan, identity_data, parent_request_id, task_id, token_usage)
            subtasks.extend(iteration_results)
            for item in iteration_results:
                yield self._checkpoint("subtask_done", checkpoints, identity, parent_request_id, task_id, item)

            response = self._combine(prompt, iteration_results, identity_data, parent_request_id, task_id, token_usage)
            yield self._checkpoint("combine_ready", checkpoints, identity, parent_request_id, task_id, {"response": response})
            decision = self._evaluate(prompt, response, identity_data, parent_request_id, task_id, token_usage)
            yield self._checkpoint(
                "iteration_end", checkpoints, identity, parent_request_id, task_id,
                {"iteration": iterations, "decision": decision},
            )

            stop_reason = self._limit_reason(started, token_usage)
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
                plan = self._plan(prompt, identity_data, parent_request_id, task_id, token_usage)
                continue
            if iterations >= self.settings.max_iterations:
                stop_reason = "max_iterations"
                break

        tokens_in, tokens_out = token_usage.snapshot()
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
                "tokens_in": tokens_in,
                "tokens_out": tokens_out,
                "stop_reason": stop_reason,
            },
            "checkpoints": [*checkpoints, "task_done"],
        }
        yield self._checkpoint("task_done", checkpoints, identity, parent_request_id, task_id, payload)

    def _stream_coverage(
        self,
        *,
        prompt: str,
        identity_override: dict[str, str] | None,
        request_id: str | None,
    ) -> Iterator[Event]:
        started = time.monotonic()
        parent_request_id = request_id or str(uuid4())
        task_id = str(uuid4())
        identity_data = dict(identity_override or {})
        identity = Identity.from_defaults(self.config.identity_defaults, identity_data)
        checkpoints: list[str] = []
        token_usage = _TokenUsage()
        coverage_settings = self.settings.coverage
        if coverage_settings is None:
            raise CoreError("ConfigError", "coverage configuration is required", "orchestration.coverage")

        yield self._checkpoint(
            "task_received",
            checkpoints,
            identity,
            parent_request_id,
            task_id,
            {"prompt": prompt},
        )
        plan = self._plan_coverage(prompt, identity_data, parent_request_id, task_id, token_usage)
        ledger = _CoverageLedger(plan, token_usage)
        units_payload = [self._coverage_unit_plan_record(unit) for unit in plan]
        yield self._checkpoint(
            "plan_ready",
            checkpoints,
            identity,
            parent_request_id,
            task_id,
            {"units": units_payload},
        )

        if len(plan) > self.settings.max_subtasks:
            stop_reason = "max_subtasks"
        else:
            stop_reason = ""

        cycle = 0
        while not stop_reason:
            stop_reason = self._coverage_limit_reason(started, ledger)
            if stop_reason:
                break

            eligible = self._coverage_eligible_units(ledger)
            if not eligible:
                stop_reason = "no_progress"
                break

            selected = eligible[:coverage_settings.units_per_chunk]
            remaining_chunks = coverage_settings.max_chunks - ledger.chunk_index
            groups = self._coverage_groups(selected, ledger, remaining_chunks)
            if not groups:
                stop_reason = "max_chunks"
                break

            cycle += 1
            generations = self._generate_coverage_groups(
                prompt,
                groups,
                identity_data,
                parent_request_id,
                task_id,
                token_usage,
            )
            completed_before = len(ledger.completed_ids())
            accepted_records: list[dict[str, Any]] = []
            for generation in generations:
                records = self._validate_coverage_generation(
                    generation,
                    prompt,
                    identity_data,
                    parent_request_id,
                    task_id,
                    ledger,
                )
                accepted_records.extend(records)

            for record in sorted(accepted_records, key=lambda item: int(item["index"])):
                yield self._checkpoint(
                    "subtask_done",
                    checkpoints,
                    identity,
                    parent_request_id,
                    task_id,
                    record,
                )

            for chunk in self._coverage_emittable_chunks(ledger):
                yield self._checkpoint(
                    "answer_chunk",
                    checkpoints,
                    identity,
                    parent_request_id,
                    task_id,
                    chunk,
                    json_only=True,
                )

            completed_after = len(ledger.completed_ids())
            if completed_after == completed_before:
                ledger.no_progress_iterations += 1
            else:
                ledger.no_progress_iterations = 0

            snapshot = self._coverage_snapshot(ledger)
            yield self._checkpoint(
                "coverage_updated",
                checkpoints,
                identity,
                parent_request_id,
                task_id,
                snapshot,
                json_only=True,
            )
            yield self._checkpoint(
                "iteration_end",
                checkpoints,
                identity,
                parent_request_id,
                task_id,
                {"iteration": cycle, "coverage": snapshot},
            )

            if not ledger.pending_ids() and not ledger.failed_ids():
                stop_reason = "task_done"

        response = self._assemble_coverage(ledger)
        yield self._checkpoint(
            "combine_ready",
            checkpoints,
            identity,
            parent_request_id,
            task_id,
            {"response": response},
        )
        tokens_in, tokens_out = token_usage.snapshot()
        coverage = self._coverage_result(ledger, stop_reason == "task_done")
        payload = {
            "response": response,
            "stop_reason": stop_reason,
            "subtasks": self._coverage_subtasks(ledger),
            "params": self._coverage_params(),
            "trace": {
                "request_id": parent_request_id,
                "task_id": task_id,
                "capability": "task.run",
                **identity.to_dict(),
                "latency_ms": int((time.monotonic() - started) * 1000),
                "tokens_in": tokens_in,
                "tokens_out": tokens_out,
                "stop_reason": stop_reason,
                "mode": "coverage",
            },
            "checkpoints": [*checkpoints, "task_done"],
            "mode": "coverage",
            "coverage": coverage,
            "chunks": self._ordered_coverage_chunks(ledger),
        }
        yield self._checkpoint(
            "task_done",
            checkpoints,
            identity,
            parent_request_id,
            task_id,
            payload,
        )

    def _plan_coverage(
        self,
        prompt: str,
        identity: dict[str, str],
        parent: str,
        task_id: str,
        token_usage: _TokenUsage,
    ) -> list[_CoverageUnit]:
        domain_ids = ", ".join(domain.id for domain in self.config.domains)
        instruction = (
            "Derive the coverage units of the task. Create one unit per verifiable item "
            "(each enumerable element, requirement or part gets its own unit). Return only "
            "a JSON list of objects with a short string id, prompt, optional domain_hint "
            "and optional depends_on as a list of ids. If domain_hint is used, it must be "
            f"one of: {domain_ids}. Task: {prompt}"
        )
        result = self._run_target(
            self.settings.planner,
            instruction,
            identity,
            parent,
            task_id,
            "planner",
            token_usage,
        )
        raw_plan = _parse_plan(result.response)
        if not isinstance(raw_plan, list):
            raise CoreError("PlanParseError", "planner returned an invalid coverage plan", "plan")

        units: list[_CoverageUnit] = []
        ids: set[str] = set()
        for position, item in enumerate(raw_plan, start=1):
            if not isinstance(item, dict):
                raise CoreError("PlanParseError", "planner returned an invalid coverage unit", "plan")
            unit_id = _coerce_unit_id(item.get("id")) or f"u{position}"
            unit_prompt = item.get("prompt")
            if unit_id in ids:
                raise CoreError("PlanParseError", "coverage unit ids must be unique and non-empty", "id")
            if not isinstance(unit_prompt, str) or not unit_prompt.strip():
                raise CoreError("PlanParseError", "coverage unit prompt must be non-empty", "prompt")
            depends_on = item.get("depends_on", [])
            if depends_on is None:
                depends_on = []
            if not isinstance(depends_on, list):
                raise CoreError(
                    "PlanDependencyError",
                    "depends_on must contain coverage unit ids",
                    "depends_on",
                )
            coerced_depends = [_coerce_unit_id(dependency) for dependency in depends_on]
            if not all(coerced_depends):
                raise CoreError(
                    "PlanDependencyError",
                    "depends_on must contain coverage unit ids",
                    "depends_on",
                )
            ids.add(unit_id)
            units.append(
                _CoverageUnit(
                    id=unit_id,
                    prompt=unit_prompt,
                    depends_on=[dependency for dependency in coerced_depends if dependency],
                    domain_hint=item.get("domain_hint") if isinstance(item.get("domain_hint"), str) else None,
                )
            )

        self._validate_coverage_dependencies(units)
        for unit in units:
            self._resolve_coverage_unit(unit)
        return units

    def _validate_coverage_dependencies(self, units: list[_CoverageUnit]) -> None:
        ids = {unit.id for unit in units}
        if any(dependency not in ids for unit in units for dependency in unit.depends_on):
            raise CoreError(
                "PlanDependencyError",
                "coverage dependencies must reference existing ids",
                "depends_on",
            )
        dependencies = {unit.id: set(unit.depends_on) for unit in units}
        remaining = set(dependencies)
        completed: set[str] = set()
        while remaining:
            ready = {unit_id for unit_id in remaining if dependencies[unit_id].issubset(completed)}
            if not ready:
                raise CoreError("PlanDependencyError", "coverage plan contains a cycle", "depends_on")
            completed.update(ready)
            remaining.difference_update(ready)

    def _resolve_coverage_unit(self, unit: _CoverageUnit) -> None:
        domain_id = self._resolve_domain_hint(unit.domain_hint)
        if unit.domain_hint and domain_id is None:
            unit.domain_hint_ignored = unit.domain_hint
        if domain_id is None:
            resolved = self.prompt_runtime.router.route(unit.prompt).resolved
        else:
            resolved = self.prompt_runtime.registry.resolve_domain_model(domain_id)
        unit.domain = resolved.domain.id if resolved.domain is not None else ""
        unit.model = resolved.model.id

    def _coverage_eligible_units(self, ledger: _CoverageLedger) -> list[_CoverageUnit]:
        completed = set(ledger.completed_ids())
        return [
            unit
            for unit in ledger.units
            if unit.state == "pending" and set(unit.depends_on).issubset(completed)
        ]

    def _coverage_groups(
        self,
        units: list[_CoverageUnit],
        ledger: _CoverageLedger,
        limit: int,
    ) -> list[_CoverageGroup]:
        grouped: dict[tuple[str, str], list[_CoverageUnit]] = {}
        for unit in units:
            grouped.setdefault((unit.domain, unit.model), []).append(unit)
        groups: list[_CoverageGroup] = []
        for (domain, model), group_units in list(grouped.items())[:limit]:
            ledger.chunk_index += 1
            groups.append(
                _CoverageGroup(
                    chunk_index=ledger.chunk_index,
                    units=group_units,
                    domain=domain,
                    model=model,
                    completed_ids=ledger.completed_ids(),
                )
            )
        return groups

    def _generate_coverage_groups(
        self,
        objective: str,
        groups: list[_CoverageGroup],
        identity: dict[str, str],
        parent: str,
        task_id: str,
        token_usage: _TokenUsage,
    ) -> list[_CoverageGeneration]:
        with ThreadPoolExecutor(max_workers=min(self.settings.max_parallel, len(groups))) as executor:
            futures = [
                executor.submit(
                    self._run_coverage_generator,
                    objective,
                    group,
                    identity,
                    parent,
                    task_id,
                    token_usage,
                )
                for group in groups
            ]
            return [future.result() for future in futures]

    def _run_coverage_generator(
        self,
        objective: str,
        group: _CoverageGroup,
        identity: dict[str, str],
        parent: str,
        task_id: str,
        token_usage: _TokenUsage,
    ) -> _CoverageGeneration:
        request_id = str(uuid4())
        unit_ids = [unit.id for unit in group.units]
        content = self._coverage_generation_prompt(objective, group.units, group.completed_ids)
        trace_payload = {
            "task_id": task_id,
            "parent_request_id": parent,
            "orchestration_role": "generator",
            "chunk_index": group.chunk_index,
            "unit_ids": unit_ids,
        }
        ignored = [unit.domain_hint_ignored for unit in group.units if unit.domain_hint_ignored]
        if ignored:
            trace_payload["domain_hint_ignored"] = ignored[0] if len(ignored) == 1 else ignored
        try:
            result = self._run_prompt(
                prompt=content,
                domain_id=group.domain,
                identity=identity,
                request_id=request_id,
                trace_payload=trace_payload,
                token_usage=token_usage,
            )
        except CoreError as exc:
            return _CoverageGeneration(group, request_id, None, exc)
        return _CoverageGeneration(group, request_id, result)

    def _coverage_generation_prompt(
        self,
        objective: str,
        units: list[_CoverageUnit],
        completed_ids: list[str],
    ) -> str:
        targets = [{"id": unit.id, "prompt": unit.prompt} for unit in units]
        completed_text = ", ".join(completed_ids) if completed_ids else "none"
        return (
            f"Objective: {objective}\n"
            f"Target coverage units: {json.dumps(targets, ensure_ascii=False)}\n"
            f"Completed unit references: {completed_text}\n"
            "Answer only the target units. Do not repeat completed units."
        )

    def _validate_coverage_generation(
        self,
        generation: _CoverageGeneration,
        objective: str,
        identity: dict[str, str],
        parent: str,
        task_id: str,
        ledger: _CoverageLedger,
    ) -> list[dict[str, Any]]:
        targets = generation.group.units
        if generation.result is None:
            self._record_failed_coverage_attempts(targets)
            return []

        unit_ids = [unit.id for unit in targets]
        content = (
            "Validate coverage. Return only a JSON list containing the ids actually covered. "
            f"Objective: {objective}\n"
            f"Target units: {json.dumps([{'id': unit.id, 'prompt': unit.prompt} for unit in targets], ensure_ascii=False)}\n"
            f"Fragment: {generation.result.response}"
        )
        coverage_settings = self.settings.coverage
        if coverage_settings is None:
            raise CoreError("ConfigError", "coverage configuration is required", "orchestration.coverage")
        try:
            validation = self._run_prompt(
                prompt=content,
                model_id=coverage_settings.validator.model,
                domain_id=coverage_settings.validator.domain,
                profile_id=coverage_settings.validator.profile,
                identity=identity,
                request_id=str(uuid4()),
                trace_payload={
                    "task_id": task_id,
                    "parent_request_id": parent,
                    "orchestration_role": "validator",
                    "chunk_index": generation.group.chunk_index,
                    "unit_ids": unit_ids,
                },
                token_usage=ledger.token_usage,
            )
            covered = _parse_covered_ids(validation.response)
        except CoreError:
            self._record_failed_coverage_attempts(targets)
            return []

        target_by_id = {unit.id: unit for unit in targets}
        accepted_ids = [
            unit.id
            for unit in ledger.units
            if unit.id in covered and unit.id in target_by_id and unit.state == "pending"
        ]
        accepted_set = set(accepted_ids)
        for unit in targets:
            if unit.id not in accepted_set and unit.state == "pending":
                self._record_failed_coverage_attempts([unit])

        if not accepted_ids:
            return []

        result = generation.result
        chunk = {
            "chunk_index": generation.group.chunk_index,
            "unit_ids": accepted_ids,
            "text": result.response,
            "_domain": result.domain,
            "_model": result.model,
            "_finish_reason": result.trace.get("finish_reason"),
            "_request_id": generation.request_id,
            "_task_id": task_id,
            "_parent_request_id": parent,
            "_substituted": bool(result.trace.get("substituted")),
        }
        ledger.chunks.append(chunk)
        records: list[dict[str, Any]] = []
        index_by_id = {unit.id: index for index, unit in enumerate(ledger.units)}
        for unit_id in accepted_ids:
            unit = target_by_id[unit_id]
            unit.state = "completed"
            unit.domain = result.domain
            unit.model = result.model
            unit.fragment = chunk
            record = {
                "index": index_by_id[unit.id],
                "prompt": unit.prompt,
                "response": result.response,
                "domain": result.domain,
                "model": result.model,
                "finish_reason": result.trace.get("finish_reason"),
                "substituted": bool(result.trace.get("substituted")),
                "request_id": generation.request_id,
                "task_id": task_id,
                "parent_request_id": parent,
                "unit_id": unit.id,
            }
            if unit.domain_hint_ignored is not None:
                record["domain_hint_ignored"] = unit.domain_hint_ignored
            records.append(record)
        return records

    def _record_failed_coverage_attempts(self, units: list[_CoverageUnit]) -> None:
        coverage_settings = self.settings.coverage
        if coverage_settings is None:
            raise CoreError("ConfigError", "coverage configuration is required", "orchestration.coverage")
        failed_at = 1 + coverage_settings.max_retries_per_unit
        for unit in units:
            if unit.state != "pending":
                continue
            unit.retries += 1
            if unit.retries >= failed_at:
                unit.state = "failed"

    def _coverage_emittable_chunks(self, ledger: _CoverageLedger) -> list[dict[str, Any]]:
        completed = set(ledger.completed_ids())
        contiguous: set[str] = set()
        for unit in ledger.units:
            if unit.id not in completed:
                break
            contiguous.add(unit.id)

        emitted: list[dict[str, Any]] = []
        for chunk in self._ordered_internal_chunks(ledger):
            chunk_index = int(chunk["chunk_index"])
            if chunk_index in ledger.emitted_chunk_indexes:
                continue
            if not set(chunk["unit_ids"]).issubset(contiguous):
                break
            ledger.emitted_chunk_indexes.add(chunk_index)
            emitted.append(self._public_chunk(chunk))
        return emitted

    def _coverage_snapshot(self, ledger: _CoverageLedger) -> dict[str, Any]:
        tokens_in, tokens_out = ledger.token_usage.snapshot()
        return {
            "completed": ledger.completed_ids(),
            "pending": ledger.pending_ids(),
            "failed": ledger.failed_ids(),
            "chunk_index": ledger.chunk_index,
            "retries": {unit.id: unit.retries for unit in ledger.units},
            "tokens_in": tokens_in,
            "tokens_out": tokens_out,
        }

    def _coverage_limit_reason(self, started: float, ledger: _CoverageLedger) -> str | None:
        coverage_settings = self.settings.coverage
        if coverage_settings is None:
            raise CoreError("ConfigError", "coverage configuration is required", "orchestration.coverage")
        elapsed = float(self.simulated.get("elapsed_s", time.monotonic() - started))
        total_tokens = (
            int(self.simulated["context_tokens"])
            if "context_tokens" in self.simulated
            else ledger.token_usage.total()
        )
        if elapsed >= self.settings.max_time_s:
            return "max_time"
        if total_tokens >= coverage_settings.max_total_tokens:
            return "max_total_tokens"
        if ledger.chunk_index >= coverage_settings.max_chunks:
            return "max_chunks"
        if ledger.no_progress_iterations >= coverage_settings.max_no_progress_iterations:
            return "no_progress"
        if ledger.units and not self._coverage_eligible_units(ledger):
            return "no_progress"
        return None

    def _assemble_coverage(self, ledger: _CoverageLedger) -> str:
        return "".join(str(chunk["text"]) for chunk in self._ordered_internal_chunks(ledger))

    def _ordered_internal_chunks(self, ledger: _CoverageLedger) -> list[dict[str, Any]]:
        index_by_id = {unit.id: index for index, unit in enumerate(ledger.units)}
        return sorted(
            ledger.chunks,
            key=lambda chunk: min(index_by_id[unit_id] for unit_id in chunk["unit_ids"]),
        )

    def _ordered_coverage_chunks(self, ledger: _CoverageLedger) -> list[dict[str, Any]]:
        return [self._public_chunk(chunk) for chunk in self._ordered_internal_chunks(ledger)]

    @staticmethod
    def _public_chunk(chunk: dict[str, Any]) -> dict[str, Any]:
        return {
            "chunk_index": chunk["chunk_index"],
            "unit_ids": list(chunk["unit_ids"]),
            "text": chunk["text"],
        }

    def _coverage_result(self, ledger: _CoverageLedger, coverage_complete: bool) -> dict[str, Any]:
        tokens_in, tokens_out = ledger.token_usage.snapshot()
        return {
            "coverage_complete": coverage_complete,
            "completed_units": ledger.completed_ids(),
            "failed_units": ledger.failed_ids(),
            "pending_units": ledger.pending_ids(),
            "chunk_index": ledger.chunk_index,
            "units": [
                {"id": unit.id, "domain": unit.domain, "model": unit.model}
                for unit in ledger.units
            ],
            "retries": {unit.id: unit.retries for unit in ledger.units},
            "tokens_in": tokens_in,
            "tokens_out": tokens_out,
        }

    def _coverage_subtasks(self, ledger: _CoverageLedger) -> list[dict[str, Any]]:
        records: list[dict[str, Any]] = []
        for index, unit in enumerate(ledger.units):
            if unit.fragment is None:
                continue
            records.append(
                {
                    "index": index,
                    "prompt": unit.prompt,
                    "response": unit.fragment["text"],
                    "domain": unit.fragment["_domain"],
                    "model": unit.fragment["_model"],
                    "finish_reason": unit.fragment["_finish_reason"],
                    "substituted": unit.fragment["_substituted"],
                    "request_id": unit.fragment["_request_id"],
                    "task_id": unit.fragment["_task_id"],
                    "parent_request_id": unit.fragment["_parent_request_id"],
                    "unit_id": unit.id,
                }
            )
        return records

    def _coverage_params(self) -> dict[str, Any]:
        coverage_settings = self.settings.coverage
        if coverage_settings is None:
            raise CoreError("ConfigError", "coverage configuration is required", "orchestration.coverage")
        return {
            "max_subtasks": self.settings.max_subtasks,
            "max_time_s": self.settings.max_time_s,
            "max_parallel": self.settings.max_parallel,
            "units_per_chunk": coverage_settings.units_per_chunk,
            "max_chunks": coverage_settings.max_chunks,
            "max_total_tokens": coverage_settings.max_total_tokens,
            "max_retries_per_unit": coverage_settings.max_retries_per_unit,
            "max_no_progress_iterations": coverage_settings.max_no_progress_iterations,
        }

    @staticmethod
    def _coverage_unit_plan_record(unit: _CoverageUnit) -> dict[str, Any]:
        record: dict[str, Any] = {"id": unit.id, "prompt": unit.prompt}
        if unit.domain_hint is not None:
            record["domain_hint"] = unit.domain_hint
        if unit.depends_on:
            record["depends_on"] = list(unit.depends_on)
        return record

    def _plan(self, prompt: str, identity: dict[str, str], parent: str, task_id: str, token_usage: _TokenUsage) -> list[dict[str, Any]]:
        domain_ids = ", ".join(domain.id for domain in self.config.domains)
        instruction = (
            "Decompose the task. Return only a JSON list of objects with prompt and optional "
            "domain_hint and depends_on. If domain_hint is used, it must be one of: "
            f"{domain_ids}. Task: {prompt}"
        )
        result = self._run_target(self.settings.planner, instruction, identity, parent, task_id, "planner", token_usage)
        plan = _parse_plan(result.response)
        if not isinstance(plan, list) or not all(self._valid_subtask(item) for item in plan):
            raise CoreError("PlanParseError", "planner returned an invalid plan", "plan")
        return [dict(item) for item in plan]

    def _fan_out(self, plan: list[dict[str, Any]], identity: dict[str, str], parent: str, task_id: str, token_usage: _TokenUsage) -> list[dict[str, Any]]:
        pending = set(range(len(plan)))
        completed: dict[int, dict[str, Any]] = {}
        while pending:
            ready = [index for index in sorted(pending) if self._dependencies(plan[index]).issubset(completed)]
            if not ready:
                raise CoreError("PlanDependencyError", "plan contains cyclic or invalid dependencies", "depends_on")
            with ThreadPoolExecutor(max_workers=self.settings.max_parallel) as executor:
                futures = {
                    index: executor.submit(self._run_subtask, index, plan[index], identity, parent, task_id, token_usage)
                    for index in ready
                }
                for index in ready:
                    completed[index] = futures[index].result()
                    pending.remove(index)
        return [completed[index] for index in range(len(plan))]

    def _run_subtask(self, index: int, item: dict[str, Any], identity: dict[str, str], parent: str, task_id: str, token_usage: _TokenUsage) -> dict[str, Any]:
        domain_hint = item.get("domain_hint")
        domain_id = self._resolve_domain_hint(domain_hint)
        ignored_hint = domain_hint if domain_hint and domain_id is None else None
        request_id = str(uuid4())
        trace_payload = {"task_id": task_id, "parent_request_id": parent, "subtask_index": index}
        if ignored_hint is not None:
            trace_payload["domain_hint_ignored"] = ignored_hint
        result = self._run_prompt(
            prompt=str(item["prompt"]), domain_id=domain_id,
            identity=identity, request_id=request_id, trace_payload=trace_payload, token_usage=token_usage,
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

    def _combine(self, prompt: str, results: list[dict[str, Any]], identity: dict[str, str], parent: str, task_id: str, token_usage: _TokenUsage) -> str:
        content = f"Combine the subtask results into one answer. Task: {prompt}\nResults: {json.dumps(results, ensure_ascii=False)}"
        return self._run_target(self.settings.combiner, content, identity, parent, task_id, "combiner", token_usage).response

    def _evaluate(self, prompt: str, response: str, identity: dict[str, str], parent: str, task_id: str, token_usage: _TokenUsage) -> str:
        content = (
            "Evaluate the combined answer. Return only one word: done, rerun, or replan. "
            f"Task: {prompt}\nAnswer: {response}"
        )
        response_text = self._run_target(
            self.settings.planner, content, identity, parent, task_id, "evaluator", token_usage
        ).response
        return _parse_evaluation_decision(response_text)

    def _run_target(self, target: OrchestrationTargetConfig, prompt: str, identity: dict[str, str], parent: str, task_id: str, role: str, token_usage: _TokenUsage) -> PromptRunResult:
        return self._run_prompt(
            prompt=prompt, model_id=target.model, domain_id=target.domain, profile_id=target.profile,
            identity=identity, request_id=str(uuid4()),
            trace_payload={"task_id": task_id, "parent_request_id": parent, "orchestration_role": role},
            token_usage=token_usage,
        )

    def _run_prompt(self, **kwargs: Any) -> PromptRunResult:
        result = self.prompt_runtime.run(
            prompt=kwargs["prompt"], model_id=kwargs.get("model_id"), domain_id=kwargs.get("domain_id"),
            profile_id=kwargs.get("profile_id"), identity_override=kwargs["identity"],
            request_id=kwargs["request_id"], trace_payload=kwargs["trace_payload"],
        )
        kwargs["token_usage"].add(result)
        return result

    def _checkpoint(
        self,
        name: str,
        checkpoints: list[str],
        identity: Identity,
        parent: str,
        task_id: str,
        data: dict[str, Any],
        json_only: bool = False,
    ) -> Event:
        checkpoints.append(name)
        payload = {"task_id": task_id, "parent_request_id": parent, **data}
        self.prompt_runtime.telemetry.record(
            request_id=parent,
            event=name,
            capability="task.run",
            identity=identity,
            payload=payload,
            csv_event=not json_only,
        )
        return Event(name, data)

    def _limit_reason(self, started: float, token_usage: _TokenUsage) -> str | None:
        elapsed = float(self.simulated.get("elapsed_s", time.monotonic() - started))
        context = int(self.simulated["context_tokens"]) if "context_tokens" in self.simulated else token_usage.total()
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


def _coerce_unit_id(value: Any) -> str | None:
    if isinstance(value, bool):
        return None
    if isinstance(value, int):
        return str(value)
    if isinstance(value, str) and value.strip():
        return value.strip()
    return None


def _parse_covered_ids(text: str) -> set[str]:
    without_fences = re.sub(r"```(?:json)?\s*", "", text, flags=re.IGNORECASE)
    without_fences = without_fences.replace("```", "").strip()
    candidates = [without_fences]
    starts = [
        index
        for index, character in enumerate(without_fences)
        if character in "[{"
    ]
    candidates.extend(without_fences[index:] for index in starts)
    value: Any = None
    for candidate in candidates:
        try:
            value, _ = json.JSONDecoder().raw_decode(candidate)
            break
        except json.JSONDecodeError:
            continue
    if isinstance(value, dict):
        for key in ("ids", "unit_ids", "completed_units", "covered"):
            if key in value:
                value = value[key]
                break
    if not isinstance(value, list):
        return set()
    return {item for item in value if isinstance(item, str)}


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
