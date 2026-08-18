from __future__ import annotations

import json
import re
import string
import time
from copy import copy
from concurrent.futures import ThreadPoolExecutor
from dataclasses import dataclass, field, replace
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
    token_budget_total: int
    mode: str | None = None
    coverage: dict[str, Any] | None = None
    chunks: list[dict[str, Any]] | None = None
    requirements_covered: bool = False
    uncovered_requirements: list[str] = field(default_factory=list)
    degradations: list[dict[str, str]] = field(default_factory=list)
    plan_attempts: int = 1
    evaluation_attempts: int = 1

    def to_dict(self) -> dict[str, Any]:
        result = {
            "response": self.response,
            "stop_reason": self.stop_reason,
            "subtasks": self.subtasks,
            "params": self.params,
            "trace": self.trace,
            "checkpoints": self.checkpoints,
            "token_budget_total": self.token_budget_total,
        }
        if self.mode is not None:
            result["mode"] = self.mode
        if self.coverage is not None:
            result["coverage"] = self.coverage
        if self.chunks is not None:
            result["chunks"] = self.chunks
        result["requirements_covered"] = self.requirements_covered
        result["uncovered_requirements"] = self.uncovered_requirements
        result["degradations"] = self.degradations
        result["plan_attempts"] = self.plan_attempts
        result["evaluation_attempts"] = self.evaluation_attempts
        return result


@dataclass(frozen=True)
class TaskPlanResult:
    plan: list[dict[str, Any]]
    requirements: list[dict[str, Any]]
    degradations: list[dict[str, str]]
    effort: str
    params: dict[str, Any]
    trace: dict[str, Any]

    def to_dict(self) -> dict[str, Any]:
        return {
            "plan": self.plan,
            "requirements": self.requirements,
            "degradations": self.degradations,
            "effort": self.effort,
            "params": self.params,
            "trace": self.trace,
        }


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
    domain: str = ""
    model: str = ""
    retries: int = 0
    state: str = "pending"
    fragment: dict[str, Any] | None = None
    covers: list[str] = field(default_factory=list)


@dataclass(frozen=True)
class _PlanAttempt:
    plan: list[dict[str, Any]]
    requirements: list[dict[str, str]]
    requirements_covered: bool
    uncovered_requirements: list[str]


@dataclass(frozen=True)
class _PlanResolution:
    attempts: list[_PlanAttempt]
    degradations: list[dict[str, str]]

    @property
    def final(self) -> _PlanAttempt:
        return self.attempts[-1]


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
        self.resolved_effort = "medium"
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
        effort: str | None = None,
        plan: list[dict[str, Any]] | None = None,
        requirements: list[dict[str, Any]] | None = None,
    ) -> TaskResult:
        events = list(
            self.stream(
                prompt=prompt,
                identity_override=identity_override,
                request_id=request_id,
                mode=mode,
                effort=effort,
                plan=plan,
                requirements=requirements,
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
        effort: str | None = None,
        plan: list[dict[str, Any]] | None = None,
        requirements: list[dict[str, Any]] | None = None,
    ) -> Iterator[Event]:
        runtime = self._runtime_for_effort(effort)
        yield from runtime._stream_resolved(
            prompt=prompt,
            identity_override=identity_override,
            request_id=request_id,
            mode=mode,
            plan=plan,
            requirements=requirements,
        )

    def plan(
        self,
        *,
        prompt: str,
        identity_override: dict[str, str] | None = None,
        request_id: str | None = None,
        effort: str | None = None,
    ) -> TaskPlanResult:
        runtime = self._runtime_for_effort(effort)
        started = time.monotonic()
        parent_request_id = request_id or str(uuid4())
        task_id = str(uuid4())
        identity_data = dict(identity_override or {})
        identity = Identity.from_defaults(runtime.config.identity_defaults, identity_data)
        token_usage = _TokenUsage()
        resolution = runtime._plan(
            prompt,
            identity_data,
            parent_request_id,
            task_id,
            token_usage,
            allow_renegotiation=True,
        )
        tokens_in, tokens_out = token_usage.snapshot()
        return TaskPlanResult(
            plan=runtime._public_pipeline_plan(resolution.final.plan),
            requirements=resolution.final.requirements,
            degradations=resolution.degradations,
            effort=runtime.resolved_effort,
            params=runtime._params(),
            trace={
                "request_id": parent_request_id,
                "task_id": task_id,
                "capability": "task.plan",
                **identity.to_dict(),
                "latency_ms": int((time.monotonic() - started) * 1000),
                "tokens_in": tokens_in,
                "tokens_out": tokens_out,
            },
        )

    def _stream_resolved(
        self,
        *,
        prompt: str,
        identity_override: dict[str, str] | None,
        request_id: str | None,
        mode: str,
        plan: list[dict[str, Any]] | None,
        requirements: list[dict[str, Any]] | None,
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
        degradations: list[dict[str, str]] = []
        plan_renegotiation_used = False
        evaluation_renegotiation_used = False

        yield self._checkpoint("task_received", checkpoints, identity, parent_request_id, task_id, {"prompt": prompt})
        plan_source = "supplied" if plan is not None else "planner"
        if plan_source == "supplied":
            plan_resolution = self._supplied_plan_resolution(plan, requirements)
        else:
            plan_resolution = self._plan(
                prompt,
                identity_data,
                parent_request_id,
                task_id,
                token_usage,
                allow_renegotiation=True,
            )
            plan_renegotiation_used = len(plan_resolution.attempts) == 2
        degradations.extend(plan_resolution.degradations)
        token_budget_granted = self._pipeline_token_grant(plan_resolution.final.plan)
        token_budget_total = token_budget_granted

        for attempt_number, attempt in enumerate(plan_resolution.attempts, start=1):
            yield self._checkpoint(
                "plan_ready",
                checkpoints,
                identity,
                parent_request_id,
                task_id,
                self._plan_ready_payload(
                    "plan", attempt, 0 if plan_source == "supplied" else attempt_number,
                    token_budget_granted, token_budget_total, plan_source=plan_source,
                ),
            )

        while True:
            plan = plan_resolution.final.plan
            if len(plan) > self.settings.max_subtasks:
                stop_reason = "max_subtasks"
                break

            iterations += 1
            iteration_results = self._fan_out(
                prompt,
                plan,
                iterations,
                identity_data,
                parent_request_id,
                task_id,
                token_usage,
            )
            subtasks.extend(iteration_results)
            for item in iteration_results:
                yield self._checkpoint("subtask_done", checkpoints, identity, parent_request_id, task_id, item)

            response = self._combine(prompt, iteration_results, identity_data, parent_request_id, task_id, token_usage)
            yield self._checkpoint("combine_ready", checkpoints, identity, parent_request_id, task_id, {"response": response})
            decision, evaluation_attempts, evaluation_degradation = self._evaluate(
                prompt,
                response,
                identity_data,
                parent_request_id,
                task_id,
                token_usage,
                allow_renegotiation=not evaluation_renegotiation_used,
            )
            if evaluation_attempts == 2:
                evaluation_renegotiation_used = True
            if evaluation_degradation is not None:
                degradations.append(evaluation_degradation)
            yield self._checkpoint(
                "iteration_end", checkpoints, identity, parent_request_id, task_id,
                {
                    "iteration": iterations,
                    "decision": decision,
                    "evaluation_attempts": 2 if evaluation_renegotiation_used else 1,
                },
            )

            if decision == "done":
                stop_reason = "task_done"
                break
            stop_reason = self._limit_reason(started, token_usage, token_budget_total)
            if stop_reason:
                break
            if decision == "replan":
                if plan_source == "supplied":
                    stop_reason = "replan_unavailable"
                    break
                if replans >= self.settings.max_replans:
                    stop_reason = "max_replans"
                    break
                replans += 1
                plan_resolution = self._plan(
                    prompt,
                    identity_data,
                    parent_request_id,
                    task_id,
                    token_usage,
                    allow_renegotiation=not plan_renegotiation_used,
                )
                if len(plan_resolution.attempts) == 2:
                    plan_renegotiation_used = True
                degradations.extend(plan_resolution.degradations)
                token_budget_granted = self._pipeline_token_grant(plan_resolution.final.plan)
                token_budget_total += token_budget_granted
                for attempt_number, attempt in enumerate(plan_resolution.attempts, start=1):
                    yield self._checkpoint(
                        "plan_ready",
                        checkpoints,
                        identity,
                        parent_request_id,
                        task_id,
                        self._plan_ready_payload(
                            "plan", attempt, attempt_number,
                            token_budget_granted, token_budget_total, plan_source="planner",
                        ),
                    )
                continue
            if iterations >= self.settings.max_iterations:
                stop_reason = "max_iterations"
                break
            token_budget_total += self._pipeline_token_grant(plan)

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
                "token_budget_total": token_budget_total,
                "stop_reason": stop_reason,
            },
            "checkpoints": [*checkpoints, "task_done"],
            "requirements_covered": plan_resolution.final.requirements_covered,
            "uncovered_requirements": plan_resolution.final.uncovered_requirements,
            "degradations": degradations,
            "plan_attempts": 0 if plan_source == "supplied" else 2 if plan_renegotiation_used else 1,
            "evaluation_attempts": 2 if evaluation_renegotiation_used else 1,
            "token_budget_total": token_budget_total,
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
        plan_resolution = self._plan_coverage(
            prompt,
            identity_data,
            parent_request_id,
            task_id,
            token_usage,
            allow_renegotiation=True,
        )
        token_budget_granted = self._coverage_token_grant(plan_resolution.final.plan)
        token_budget_total = token_budget_granted
        for attempt_number, attempt in enumerate(plan_resolution.attempts, start=1):
            yield self._checkpoint(
                "plan_ready",
                checkpoints,
                identity,
                parent_request_id,
                task_id,
                self._plan_ready_payload(
                    "units", attempt, attempt_number, token_budget_granted, token_budget_total
                ),
            )
        plan = self._coverage_units_from(plan_resolution.final.plan)
        ledger = _CoverageLedger(plan, token_usage)

        if len(plan) > self.settings.max_subtasks:
            stop_reason = "max_subtasks"
        else:
            stop_reason = ""

        cycle = 0
        while not stop_reason:
            stop_reason = self._coverage_limit_reason(started, ledger, token_budget_total)
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
                {"iteration": cycle, "coverage": snapshot, "evaluation_attempts": 1},
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
                "token_budget_total": token_budget_total,
                "stop_reason": stop_reason,
                "mode": "coverage",
            },
            "checkpoints": [*checkpoints, "task_done"],
            "mode": "coverage",
            "coverage": coverage,
            "chunks": self._ordered_coverage_chunks(ledger),
            "requirements_covered": plan_resolution.final.requirements_covered,
            "uncovered_requirements": plan_resolution.final.uncovered_requirements,
            "degradations": plan_resolution.degradations,
            "plan_attempts": len(plan_resolution.attempts),
            "evaluation_attempts": 1,
            "token_budget_total": token_budget_total,
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
        *,
        allow_renegotiation: bool,
    ) -> _PlanResolution:
        domain_ids = ", ".join(domain.id for domain in self.config.domains)
        instruction = (
            "Derive the requirements and coverage units of the task in the same response. "
            "Return only a JSON object with requirements and units. Requirements must be "
            "objects with string id and text. Create one unit per verifiable item (each "
            "enumerable element, requirement or part gets its own unit). Units must have "
            "a short string id, prompt, covers as a list of requirement ids, optional domain, "
            "optional advisory domain_hint and optional depends_on as a list of unit ids. "
            f"If domain is used, it must be one of: {domain_ids}. Task: {prompt}"
        )
        return self._resolve_plan(
            prompt=prompt,
            plan_key="units",
            instruction=instruction,
            identity=identity,
            parent=parent,
            task_id=task_id,
            token_usage=token_usage,
            allow_renegotiation=allow_renegotiation,
            validate=self._validate_coverage_plan,
        )

    def _validate_coverage_plan(self, raw_plan: list[dict[str, Any]]) -> list[dict[str, Any]]:
        ids: set[str] = set()
        copied_plan: list[dict[str, Any]] = []
        for position, item in enumerate(raw_plan, start=1):
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
            copied = dict(item)
            copied["id"] = unit_id
            copied["depends_on"] = [dependency for dependency in coerced_depends if dependency]
            copied_plan.append(copied)
        dependency_units = [
            _CoverageUnit(
                id=str(item["id"]),
                prompt=str(item["prompt"]),
                depends_on=list(item["depends_on"]),
            )
            for item in copied_plan
        ]
        self._validate_coverage_dependencies(dependency_units)
        return copied_plan

    def _coverage_units_from(self, plan: list[dict[str, Any]]) -> list[_CoverageUnit]:
        units = [
            _CoverageUnit(
                id=str(item["id"]),
                prompt=str(item["prompt"]),
                depends_on=list(item.get("depends_on", [])),
                domain_hint=item.get("domain_hint") if isinstance(item.get("domain_hint"), str) else None,
                domain=item.get("domain") if isinstance(item.get("domain"), str) else "",
                covers=_string_ids(item.get("covers")),
            )
            for item in plan
        ]
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
        fixed_domain = self._configured_domain(unit.domain)
        if fixed_domain is not None:
            resolved = self.prompt_runtime.registry.resolve_domain_model(fixed_domain)
        else:
            routing_prompt = self._routing_prompt(unit.prompt, unit.domain_hint)
            resolved = self.prompt_runtime.router.route(routing_prompt).resolved
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
            f"Global objective (CONTEXT ONLY; do not answer it as a whole): {objective}\n"
            f"Assigned coverage units (the ONLY content to produce): {json.dumps(targets, ensure_ascii=False)}\n"
            f"Completed unit references: {completed_text}\n"
            "Produce ONLY the content that directly fulfills the assigned coverage units. "
            "Do not include a preamble, conclusion, transition, or meta-commentary. "
            "Do not restate or rephrase a unit prompt as an introductory sentence; "
            "emit the requested content directly. "
            "Do not address unassigned units or any other part of the global objective. "
            "Do not repeat completed units."
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
        example = json.dumps(unit_ids[:1] or ["id1"], ensure_ascii=False)
        content = (
            "You decide which target units a fragment covers. Return ONLY a JSON array of "
            "ids, taken exactly from this list and nothing else: "
            f"{json.dumps(unit_ids, ensure_ascii=False)}. Include an id if and only if the "
            "fragment addresses that unit. Do not include titles, content, explanations or "
            f"any other text; the answer must be short. Example of a valid answer: {example}.\n"
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

    def _coverage_limit_reason(
        self,
        started: float,
        ledger: _CoverageLedger,
        token_budget_total: int,
    ) -> str | None:
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
        if total_tokens >= token_budget_total:
            return "max_total_tokens"
        if ledger.chunk_index >= coverage_settings.max_chunks:
            return "max_chunks"
        if ledger.no_progress_iterations >= coverage_settings.max_no_progress_iterations:
            return "no_progress"
        if ledger.units and not self._coverage_eligible_units(ledger):
            return "no_progress"
        return None

    def _assemble_coverage(self, ledger: _CoverageLedger) -> str:
        return "\n\n".join(str(chunk["text"]).strip() for chunk in self._ordered_internal_chunks(ledger))

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
            "effort": self.resolved_effort,
            "max_subtasks": self.settings.max_subtasks,
            "max_iterations": self.settings.max_iterations,
            "max_replans": self.settings.max_replans,
            "max_time_s": self.settings.max_time_s,
            "max_parallel": self.settings.max_parallel,
            "units_per_chunk": coverage_settings.units_per_chunk,
            "max_chunks": coverage_settings.max_chunks,
            "max_retries_per_unit": coverage_settings.max_retries_per_unit,
            "max_no_progress_iterations": coverage_settings.max_no_progress_iterations,
            "token_budget": self._token_budget_params(),
        }

    @staticmethod
    def _coverage_unit_plan_record(unit: _CoverageUnit) -> dict[str, Any]:
        record: dict[str, Any] = {"id": unit.id, "prompt": unit.prompt}
        record["covers"] = list(unit.covers)
        if unit.domain:
            record["domain"] = unit.domain
        if unit.domain_hint is not None:
            record["domain_hint"] = unit.domain_hint
        if unit.depends_on:
            record["depends_on"] = list(unit.depends_on)
        return record

    def _plan(
        self,
        prompt: str,
        identity: dict[str, str],
        parent: str,
        task_id: str,
        token_usage: _TokenUsage,
        *,
        allow_renegotiation: bool,
    ) -> _PlanResolution:
        domain_ids = ", ".join(domain.id for domain in self.config.domains)
        instruction = (
            "Decompose the task and extract its requirements in the same response. Return "
            "only a JSON object with requirements and subtasks. Requirements must be "
            "objects with string id and text. Subtasks must have prompt, covers as a list "
            "of requirement ids, optional domain, optional advisory domain_hint and optional "
            "depends_on as a list of zero-based integer indexes into this same list. If domain is "
            f"used, it must be one of: {domain_ids}. Task: {prompt}"
        )
        return self._resolve_plan(
            prompt=prompt,
            plan_key="subtasks",
            instruction=instruction,
            identity=identity,
            parent=parent,
            task_id=task_id,
            token_usage=token_usage,
            allow_renegotiation=allow_renegotiation,
            validate=self._validate_pipeline_plan,
        )

    def _supplied_plan_resolution(
        self,
        plan: list[dict[str, Any]],
        requirements: list[dict[str, Any]] | None,
    ) -> _PlanResolution:
        if not isinstance(plan, list) or not plan:
            raise CoreError("PlanParseError", "supplied plan must be a non-empty list", "plan")
        resolved_plan = self._resolve_pipeline_domains(self._validate_pipeline_plan(plan))
        if requirements is None or requirements == []:
            attempt = _PlanAttempt(resolved_plan, [], False, [])
            return _PlanResolution(
                [attempt],
                [_requirements_unavailable_degradation()],
            )
        supplied_requirements = _supplied_requirements_from(requirements)
        uncovered = _uncovered_supplied_requirement_ids(supplied_requirements, resolved_plan)
        attempt = _PlanAttempt(
            resolved_plan,
            supplied_requirements,
            not uncovered,
            uncovered,
        )
        return _PlanResolution([attempt], [])

    def _validate_pipeline_plan(self, plan: list[dict[str, Any]]) -> list[dict[str, Any]]:
        if not all(self._valid_subtask(item) for item in plan):
            raise CoreError("PlanParseError", "planner returned an invalid plan", "plan")
        copied_plan = [dict(item) for item in plan]
        self._validate_pipeline_dependencies(copied_plan)
        return copied_plan

    def _resolve_pipeline_domains(self, plan: list[dict[str, Any]]) -> list[dict[str, Any]]:
        resolved_plan: list[dict[str, Any]] = []
        for item in plan:
            resolved = dict(item)
            domain = self._configured_domain(resolved.get("domain"))
            if domain is not None:
                resolved["domain"] = domain
                if isinstance(resolved.get("domain_hint"), str) and resolved["domain_hint"].strip():
                    resolved["domain_hint_ignored"] = True
            else:
                route = self.prompt_runtime.router.route(
                    self._routing_prompt(str(resolved["prompt"]), resolved.get("domain_hint"))
                )
                resolved["domain"] = route.domain
            resolved_plan.append(resolved)
        return resolved_plan

    @staticmethod
    def _public_pipeline_plan(plan: list[dict[str, Any]]) -> list[dict[str, Any]]:
        public_plan: list[dict[str, Any]] = []
        for index, item in enumerate(plan):
            record: dict[str, Any] = {
                "index": index,
                "prompt": item["prompt"],
                "domain": item["domain"],
                "depends_on": sorted(TaskRuntime._dependencies(item)),
            }
            if item.get("domain_hint_ignored"):
                record["domain_hint_ignored"] = True
            public_plan.append(record)
        return public_plan

    def _resolve_plan(
        self,
        *,
        prompt: str,
        plan_key: str,
        instruction: str,
        identity: dict[str, str],
        parent: str,
        task_id: str,
        token_usage: _TokenUsage,
        allow_renegotiation: bool,
        validate: Callable[[list[dict[str, Any]]], list[dict[str, Any]]],
    ) -> _PlanResolution:
        attempts: list[_PlanAttempt] = []
        degradations: list[dict[str, str]] = []
        next_instruction = instruction
        maximum_attempts = 2 if allow_renegotiation else 1
        for attempt_number in range(1, maximum_attempts + 1):
            result = self._run_target(
                self.settings.planner,
                next_instruction,
                identity,
                parent,
                task_id,
                "planner",
                token_usage,
            )
            try:
                parsed = _parse_plan(result.response)
                raw_plan, raw_requirements = _plan_lists_from(parsed, plan_key)
                plan = validate(raw_plan)
                if plan_key == "subtasks":
                    plan = self._resolve_pipeline_domains(plan)
            except CoreError as exc:
                if exc.type != "PlanParseError":
                    raise
                attempts.append(_PlanAttempt([], [], False, []))
                if attempt_number < maximum_attempts:
                    next_instruction = self._plan_renegotiation_instruction(
                        instruction,
                        shape_invalid=True,
                        too_large=False,
                        uncovered=[],
                        requirements_missing=False,
                    )
                    continue
                plan = [{"prompt": prompt, "domain": self.config.default_domain or "general"}]
                if plan_key == "units":
                    plan[0]["id"] = "u1"
                attempts[-1] = _PlanAttempt(plan, [], False, [])
                degradations.append(
                    {"stage": "plan", "reason": "unparseable_shape", "action": "single_subtask"}
                )
                break

            # Contract order inside an attempt: usable shape, I2 budget, then I1 coverage.
            too_large = len(plan) > self.settings.max_subtasks
            requirements = (
                _public_requirements_from(raw_requirements, plan)
                if plan_key == "subtasks"
                else _requirements_from(raw_requirements)
            )
            requirements_missing = raw_requirements is None or not requirements
            uncovered = _uncovered_requirement_ids(requirements, plan)
            requirements_covered = not requirements_missing and not uncovered
            attempts.append(_PlanAttempt(plan, requirements, requirements_covered, uncovered))

            needs_renegotiation = too_large or not requirements_covered
            if needs_renegotiation and attempt_number < maximum_attempts:
                next_instruction = self._plan_renegotiation_instruction(
                    instruction,
                    shape_invalid=False,
                    too_large=too_large,
                    uncovered=uncovered,
                    requirements_missing=requirements_missing,
                )
                continue
            break
        if (
            plan_key == "subtasks"
            and not attempts[-1].requirements
            and not any(item["reason"] == "requirements_unavailable" for item in degradations)
        ):
            degradations.append(_requirements_unavailable_degradation())
        return _PlanResolution(attempts, degradations)

    def _plan_renegotiation_instruction(
        self,
        instruction: str,
        *,
        shape_invalid: bool,
        too_large: bool,
        uncovered: list[str],
        requirements_missing: bool,
    ) -> str:
        defects: list[str] = []
        if shape_invalid:
            defects.append("the prior response was not a usable list in a recognized wrapper")
        if too_large:
            defects.append(
                f"the plan exceeded the explicit budget of {self.settings.max_subtasks} units; "
                "group work as needed"
            )
        if requirements_missing:
            defects.append("the prior response did not declare requirements")
        elif uncovered:
            defects.append(f"these requirement ids were uncovered: {', '.join(uncovered)}")
        return f"{instruction}\nCorrect the prior plan in one response: {'; '.join(defects)}."

    def _plan_ready_payload(
        self,
        plan_key: str,
        attempt: _PlanAttempt,
        attempt_number: int,
        token_budget_granted: int,
        token_budget_total: int,
        *,
        plan_source: str | None = None,
    ) -> dict[str, Any]:
        payload = {
            plan_key: self._public_pipeline_plan(attempt.plan) if plan_key == "plan" else attempt.plan,
            "requirements": attempt.requirements,
            "plan_attempts": attempt_number,
            "requirements_covered": attempt.requirements_covered,
            "uncovered_requirements": attempt.uncovered_requirements,
            "token_budget_granted": token_budget_granted,
            "token_budget_total": token_budget_total,
        }
        if plan_source is not None:
            payload["plan_source"] = plan_source
        return payload

    def _validate_pipeline_dependencies(self, plan: list[dict[str, Any]]) -> None:
        dependencies = {index: self._dependencies(item) for index, item in enumerate(plan)}
        if any(dependency < 0 or dependency >= len(plan) for indexes in dependencies.values() for dependency in indexes):
            raise CoreError("PlanDependencyError", "pipeline dependencies must reference valid indexes", "depends_on")
        remaining = set(dependencies)
        completed: set[int] = set()
        while remaining:
            ready = {index for index in remaining if dependencies[index].issubset(completed)}
            if not ready:
                raise CoreError("PlanDependencyError", "pipeline plan contains a cycle", "depends_on")
            completed.update(ready)
            remaining.difference_update(ready)

    def _fan_out(self, objective: str, plan: list[dict[str, Any]], iteration: int, identity: dict[str, str], parent: str, task_id: str, token_usage: _TokenUsage) -> list[dict[str, Any]]:
        pending = set(range(len(plan)))
        completed: dict[int, dict[str, Any]] = {}
        while pending:
            ready = [index for index in sorted(pending) if self._dependencies(plan[index]).issubset(completed)]
            if not ready:
                raise CoreError("PlanDependencyError", "plan contains cyclic or invalid dependencies", "depends_on")
            with ThreadPoolExecutor(max_workers=self.settings.max_parallel) as executor:
                futures = {
                    index: executor.submit(
                        self._run_subtask,
                        index,
                        iteration,
                        objective,
                        plan[index],
                        identity,
                        parent,
                        task_id,
                        token_usage,
                    )
                    for index in ready
                }
                for index in ready:
                    completed[index] = futures[index].result()
                    pending.remove(index)
        return [completed[index] for index in range(len(plan))]

    def _run_subtask(self, index: int, iteration: int, objective: str, item: dict[str, Any], identity: dict[str, str], parent: str, task_id: str, token_usage: _TokenUsage) -> dict[str, Any]:
        declared_domain = item.get("domain")
        fixed_domain = self._configured_domain(declared_domain)
        domain_hint = item.get("domain_hint")
        domain_id = fixed_domain
        if domain_id is None:
            routing_prompt = self._routing_prompt(str(item["prompt"]), domain_hint)
            route = self.prompt_runtime.router.route(routing_prompt)
            domain_id = route.domain
        request_id = str(uuid4())
        trace_payload = {
            "task_id": task_id,
            "parent_request_id": parent,
            "subtask_index": index,
            "iteration": iteration,
        }
        content = self._subtask_execution_prompt(objective, str(item["prompt"]))
        result = self._run_prompt(
            prompt=content, domain_id=domain_id,
            identity=identity, request_id=request_id, trace_payload=trace_payload, token_usage=token_usage,
        )
        record = {
            "index": index,
            "iteration": iteration,
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
        return record

    @staticmethod
    def _subtask_execution_prompt(objective: str, subtask: str) -> str:
        return (
            f"Global objective (CONTEXT ONLY; do not answer it as a whole): {objective}\n"
            f"Assigned subtask (the ONLY content to produce): {subtask}\n"
            "Produce ONLY the content that directly fulfills the assigned subtask. "
            "Do not include a preamble, conclusion, transition, or meta-commentary. "
            "Do not restate or rephrase the subtask prompt as an introductory sentence; "
            "emit the requested content directly. "
            "Do not address other subtasks or any other part of the global objective."
        )

    def _configured_domain(self, value: Any) -> str | None:
        for domain in self.config.domains:
            if isinstance(value, str) and domain.id == value:
                return domain.id
        return None

    @staticmethod
    def _routing_prompt(prompt: str, domain_hint: Any) -> str:
        if not isinstance(domain_hint, str) or not domain_hint.strip():
            return prompt
        return (
            f"{prompt}\n"
            "Advisory context from the planner; do not treat it as binding: "
            f"domain_hint={json.dumps(domain_hint, ensure_ascii=False)}"
        )

    def _combine(self, prompt: str, results: list[dict[str, Any]], identity: dict[str, str], parent: str, task_id: str, token_usage: _TokenUsage) -> str:
        content = (
            "Combine the subtask results into one internally consistent answer. "
            "When results make incompatible claims about the same point, do not present both "
            "as facts; present them as divergent versions. Do not decide which version is true "
            "or verify any claim. Do not add qualifications where the results do not diverge. "
            f"Task: {prompt}\nResults: {json.dumps(results, ensure_ascii=False)}"
        )
        return self._run_target(self.settings.combiner, content, identity, parent, task_id, "combiner", token_usage).response

    def _evaluate(
        self,
        prompt: str,
        response: str,
        identity: dict[str, str],
        parent: str,
        task_id: str,
        token_usage: _TokenUsage,
        *,
        allow_renegotiation: bool,
    ) -> tuple[str, int, dict[str, str] | None]:
        content = (
            "Evaluate the combined answer. Return only one word: done, rerun, or replan. "
            f"Task: {prompt}\nAnswer: {response}"
        )
        maximum_attempts = 2 if allow_renegotiation else 1
        for attempt_number in range(1, maximum_attempts + 1):
            response_text = self._run_target(
                self.settings.planner,
                content,
                identity,
                parent,
                task_id,
                "evaluator",
                token_usage,
            ).response
            try:
                return _parse_evaluation_decision(response_text), attempt_number, None
            except CoreError as exc:
                if exc.type != "EvaluationDecisionError":
                    raise
                if attempt_number < maximum_attempts:
                    content = (
                        "The prior response had no decipherable decision. Answer with "
                        "exactly one word and nothing else: done, rerun, or replan. "
                        "Do not explain, and do not answer the task itself. "
                        f"Task: {prompt}\nAnswer: {response}"
                    )
                    continue
                return (
                    "done",
                    attempt_number,
                    {
                        "stage": "evaluate",
                        "reason": "undecipherable_decision",
                        "action": "assume_done",
                    },
                )
        raise AssertionError("unreachable evaluator attempt loop")

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

    def _limit_reason(
        self,
        started: float,
        token_usage: _TokenUsage,
        token_budget_total: int,
    ) -> str | None:
        elapsed = float(self.simulated.get("elapsed_s", time.monotonic() - started))
        context = int(self.simulated["context_tokens"]) if "context_tokens" in self.simulated else token_usage.total()
        if elapsed >= self.settings.max_time_s:
            return "max_time"
        if context >= token_budget_total:
            return "max_total_tokens"
        return None

    def _params(self) -> dict[str, Any]:
        params = {name: getattr(self.settings, name) for name in (
            "max_subtasks", "max_iterations", "max_replans", "max_time_s", "max_parallel"
        )}
        params["effort"] = self.resolved_effort
        params["token_budget"] = self._token_budget_params()
        return params

    def _runtime_for_effort(self, requested_effort: str | None) -> TaskRuntime:
        resolved_effort = requested_effort or self.settings.default_effort
        if resolved_effort not in {"low", "medium", "high"}:
            raise CoreError(
                "ConfigError",
                "task.run effort must be low, medium or high",
                "effort",
            )

        level = self.settings.effort.get(resolved_effort)
        resolved_settings = self.settings
        if level is not None:
            replacements = {
                name: value
                for name in ("max_subtasks", "max_iterations", "max_replans", "max_time_s")
                if (value := getattr(level, name)) is not None
            }
            coverage = resolved_settings.coverage
            if coverage is not None and level.coverage is not None:
                coverage_replacements = {
                    name: value
                    for name in ("max_chunks", "max_retries_per_unit")
                    if (value := getattr(level.coverage, name)) is not None
                }
                if coverage_replacements:
                    replacements["coverage"] = replace(coverage, **coverage_replacements)
            if replacements:
                resolved_settings = replace(resolved_settings, **replacements)

        runtime = copy(self)
        runtime.settings = resolved_settings
        runtime.resolved_effort = resolved_effort
        return runtime

    def _pipeline_token_grant(self, plan: list[dict[str, Any]]) -> int:
        budget = self.settings.token_budget
        return budget.base + budget.per_subtask * len(plan)

    def _coverage_token_grant(self, plan: list[dict[str, Any]]) -> int:
        coverage_settings = self.settings.coverage
        if coverage_settings is None:
            raise CoreError("ConfigError", "coverage configuration is required", "orchestration.coverage")
        budget = self.settings.token_budget
        return (
            budget.base
            + budget.per_subtask * len(plan) * (1 + coverage_settings.max_retries_per_unit)
        )

    def _token_budget_params(self) -> dict[str, int]:
        return {
            "base": self.settings.token_budget.base,
            "per_subtask": self.settings.token_budget.per_subtask,
        }

    @staticmethod
    def _valid_subtask(item: Any) -> bool:
        return isinstance(item, dict) and isinstance(item.get("prompt"), str) and bool(item["prompt"])

    @staticmethod
    def _dependencies(item: dict[str, Any]) -> set[int]:
        value = item.get("depends_on", [])
        if value is None or value == []:
            return set()
        if isinstance(value, bool):
            raise CoreError("PlanDependencyError", "depends_on must contain subtask indexes", "depends_on")
        if isinstance(value, int):
            return {value}
        if isinstance(value, str) and value.isdecimal():
            return {int(value)}
        if isinstance(value, list):
            indexes: set[int] = set()
            for index in value:
                if isinstance(index, bool):
                    raise CoreError("PlanDependencyError", "depends_on must contain subtask indexes", "depends_on")
                if isinstance(index, int):
                    indexes.add(index)
                elif isinstance(index, str) and index.isdecimal():
                    indexes.add(int(index))
                else:
                    raise CoreError("PlanDependencyError", "depends_on must contain subtask indexes", "depends_on")
            return indexes
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


def _plan_lists_from(value: Any, preferred_key: str) -> tuple[list[dict[str, Any]], Any]:
    requirements: Any = None
    plan_value = value
    if isinstance(value, dict):
        requirements = value.get("requirements")
        plan_value = None
        for key in (preferred_key, "subtasks", "units", "plan", "steps"):
            if isinstance(value.get(key), list):
                plan_value = value[key]
                break
    if (
        not isinstance(plan_value, list)
        or not plan_value
        or not all(isinstance(item, dict) for item in plan_value)
    ):
        raise CoreError("PlanParseError", "planner returned an invalid plan shape", "plan")
    return [dict(item) for item in plan_value], requirements


def _requirements_from(value: Any) -> list[dict[str, str]]:
    if not isinstance(value, list):
        return []
    requirements: list[dict[str, str]] = []
    seen: set[str] = set()
    for item in value:
        if not isinstance(item, dict):
            return []
        requirement_id = item.get("id")
        text = item.get("text")
        if (
            not isinstance(requirement_id, str)
            or not requirement_id.strip()
            or requirement_id in seen
            or not isinstance(text, str)
            or not text.strip()
        ):
            return []
        seen.add(requirement_id)
        requirements.append({"id": requirement_id, "text": text})
    return requirements


def _requirements_unavailable_degradation() -> dict[str, str]:
    return {
        "stage": "plan",
        "reason": "requirements_unavailable",
        "action": "skip_coverage_check",
    }


def _public_requirements_from(
    value: Any,
    plan: list[dict[str, Any]],
) -> list[dict[str, Any]]:
    if isinstance(value, dict):
        value = [{"id": requirement_id, "text": text} for requirement_id, text in value.items()]
    requirements = _requirements_from(value)
    covered_by: dict[str, list[int]] = {requirement["id"]: [] for requirement in requirements}
    for index, item in enumerate(plan):
        for requirement_id in _string_ids(item.get("covers")):
            if requirement_id in covered_by:
                covered_by[requirement_id].append(index)
    return [
        {
            "id": requirement["id"],
            "statement": requirement["text"],
            "covered_by": covered_by[requirement["id"]],
        }
        for requirement in requirements
    ]


def _supplied_requirements_from(value: Any) -> list[dict[str, Any]]:
    if not isinstance(value, list):
        raise CoreError("PlanParseError", "supplied requirements must be a list", "requirements")
    requirements: list[dict[str, Any]] = []
    seen: set[str] = set()
    for item in value:
        if not isinstance(item, dict):
            raise CoreError("PlanParseError", "supplied requirements are invalid", "requirements")
        requirement_id = item.get("id")
        statement = item.get("statement")
        covered_by = item.get("covered_by")
        if (
            not isinstance(requirement_id, str)
            or not requirement_id.strip()
            or requirement_id in seen
            or not isinstance(statement, str)
            or not statement.strip()
            or not isinstance(covered_by, list)
            or any(isinstance(index, bool) or not isinstance(index, int) for index in covered_by)
        ):
            raise CoreError("PlanParseError", "supplied requirements are invalid", "requirements")
        seen.add(requirement_id)
        requirements.append(
            {"id": requirement_id, "statement": statement, "covered_by": list(covered_by)}
        )
    return requirements


def _string_ids(value: Any) -> list[str]:
    if not isinstance(value, list):
        return []
    return [item for item in value if isinstance(item, str)]


def _uncovered_requirement_ids(
    requirements: list[dict[str, Any]],
    plan: list[dict[str, Any]],
) -> list[str]:
    covered = {item for unit in plan for item in _string_ids(unit.get("covers"))}
    return [requirement["id"] for requirement in requirements if requirement["id"] not in covered]


def _uncovered_supplied_requirement_ids(
    requirements: list[dict[str, Any]],
    plan: list[dict[str, Any]],
) -> list[str]:
    valid_indexes = set(range(len(plan)))
    return [
        requirement["id"]
        for requirement in requirements
        if not set(requirement["covered_by"]) or not set(requirement["covered_by"]).issubset(valid_indexes)
    ]


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
    return _covered_ids_from(value)


def _covered_ids_from(value: Any) -> set[str]:
    if isinstance(value, dict):
        for key in ("ids", "unit_ids", "completed_units", "covered"):
            if key in value:
                return _covered_ids_from(value[key])
        return {key for key in value if isinstance(key, str)}
    if isinstance(value, list):
        ids: set[str] = set()
        for item in value:
            if isinstance(item, str):
                ids.add(item)
            elif isinstance(item, dict):
                for key in ("id", "unit_id"):
                    if isinstance(item.get(key), str):
                        ids.add(item[key])
                        break
        return ids
    return set()


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
