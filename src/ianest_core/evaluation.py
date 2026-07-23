from __future__ import annotations

import hashlib
import json
import tempfile
import time
from dataclasses import replace
from datetime import UTC, datetime
from pathlib import Path
from typing import Any
from uuid import uuid4

import yaml

from ianest_core.config import load_config, load_config_from_dict, validate_config_dict
from ianest_core.config.schema import TelemetryConfig
from ianest_core.errors import CoreError
from ianest_core.adapters import Event, ScriptedFakeAdapter
from ianest_core.registry import ModelRegistry, StaticAvailabilityProvider
from ianest_core.runtime import DomainRuntime, PromptRuntime, ReasoningRuntime, TaskRuntime

EVAL_SCHEMA_VERSION = "1"


def run_eval(
    *,
    battery_dir: str | Path = "eval/battery",
    track: str = "conformance",
    config_path: str | Path | None = None,
) -> dict[str, Any]:
    cases = _load_cases(Path(battery_dir), track)
    results = [_run_case(case, config_path=config_path) for case in cases]
    totals = _totals(results)
    conformance_digest = _conformance_digest(results)
    return {
        "run_id": str(uuid4()),
        "ts": datetime.now(UTC).isoformat(),
        "schema_version": EVAL_SCHEMA_VERSION,
        "totals": totals,
        "conformance_digest": conformance_digest,
        "verdict": "pass" if _verdict_pass(results, totals) else "fail",
        "cases": results,
    }


def _load_cases(battery_dir: Path, track: str) -> list[dict[str, Any]]:
    cases: list[dict[str, Any]] = []
    for path in sorted(battery_dir.rglob("*.yaml")):
        with path.open("r", encoding="utf-8") as handle:
            for case in yaml.safe_load(handle) or []:
                if case.get("track") == track:
                    cases.append(case)
    return cases


def _run_case(case: dict[str, Any], *, config_path: str | Path | None) -> dict[str, Any]:
    started = time.monotonic()
    try:
        result = _execute_case(case, config_path=config_path)
    except CoreError as exc:
        return _case_error(case, started, exc)
    except Exception as exc:
        return _case_error(case, started, CoreError("EvalError", str(exc), None))
    result["latency_ms"] = _latency_ms(started)
    return result


def _execute_case(case: dict[str, Any], *, config_path: str | Path | None) -> dict[str, Any]:
    capability = case.get("capability", "")
    if capability == "domain.route":
        return _execute_domain_route(case, config_path=config_path)
    if capability == "prompt.run":
        return _execute_prompt_run(case, config_path=config_path)
    if capability == "reasoning.run":
        return _execute_reasoning_run(case, config_path=config_path)
    if capability == "task.run":
        return _execute_task_run(case, config_path=config_path)
    if capability == "model.list":
        return _execute_model_list(case, config_path=config_path)
    if capability == "config.validate":
        return _execute_config_validate(case)
    raise CoreError("EvalError", f"unsupported capability {capability}", "capability")


def _execute_domain_route(case: dict[str, Any], *, config_path: str | Path | None) -> dict[str, Any]:
    config = _case_config(case, config_path=config_path)
    runtime = DomainRuntime(config, availability=_case_availability(case))
    route = runtime.route(
        prompt=case["input"].get("prompt", ""),
        identity_override=case["input"].get("identity", {}),
        request_id=case["id"],
    )
    assertions = _assertions(
        {
            "domain": route.domain,
            "model": route.model,
        },
        case.get("expect", {}),
    )
    return _case_result(case, assertions, domain=route.domain, model=route.model)


def _execute_prompt_run(case: dict[str, Any], *, config_path: str | Path | None) -> dict[str, Any]:
    config = _case_config(case, config_path=config_path)
    runtime = PromptRuntime(config, availability=_case_availability(case))
    try:
        result = runtime.run(
            prompt=case["input"].get("prompt", ""),
            model_id=case["input"].get("model"),
            domain_id=case["input"].get("domain"),
            identity_override=case["input"].get("identity", {}),
            request_id=case["id"],
        )
    except CoreError as exc:
        expected = case.get("expect", {})
        if expected.get("error_type") == exc.type:
            return _case_result(
                case,
                [{"name": "error_type", "expected": expected["error_type"], "actual": exc.type, "ok": True}],
                status="pass",
                error={"type": exc.type, "message": exc.message},
            )
        raise

    if case.get("track") == "smoke":
        metrics = {
            "latency_ms": result.trace["latency_ms"],
            "tokens_in": result.trace["tokens_in"],
            "tokens_out": result.trace["tokens_out"],
            "chars": len(result.response),
        }
        thresholds_met = _thresholds_met(
            metrics,
            case.get("thresholds", {}),
            response=result.response,
        )
        return _smoke_result(case, metrics, thresholds_met, domain=result.domain, model=result.model)

    expected = case.get("expect", {})
    actual = {
        "domain": result.domain,
        "model": result.model,
        "trace_substitution": bool(result.trace.get("substituted")),
    }
    trace_fields = expected.get("trace_fields", {})
    for key in trace_fields:
        actual[key] = result.trace.get(key)
    assertions = _assertions(actual, {**expected, **trace_fields})
    return _case_result(case, assertions, domain=result.domain, model=result.model)


def _execute_reasoning_run(case: dict[str, Any], *, config_path: str | Path | None) -> dict[str, Any]:
    config = _case_config(case, config_path=config_path)
    adapter = ScriptedFakeAdapter("fake_reasoning", _case_reasoning_responses(case))
    runtime = ReasoningRuntime(config, availability=_case_availability(case), adapter=adapter)
    result = runtime.run(
        prompt=case["input"].get("prompt", ""),
        model_id=case["input"].get("model"),
        domain_id=case["input"].get("domain"),
        identity_override=case["input"].get("identity", {}),
        request_id=case["id"],
    )
    actual = {
        "stop_reason": result.stop_reason,
        "steps": len(result.steps),
        "output": result.output,
    }
    assertions = _assertions(actual, case.get("expect", {}))
    return _case_result(case, assertions, domain=result.domain, model=result.model)


def _execute_task_run(case: dict[str, Any], *, config_path: str | Path | None) -> dict[str, Any]:
    config = _case_config(case, config_path=config_path)
    adapters = _task_adapters(case)
    script = case.get("world", {}).get("script", {})
    runtime = TaskRuntime(
        config,
        availability=_case_availability(case),
        adapter_factory=adapters.get,
        simulated=dict(script.get("simulated", {})),
    )
    expected = case.get("expect", {})
    try:
        result = runtime.run(
            prompt=case["input"].get("prompt", ""),
            mode=case["input"].get("mode", "pipeline"),
            identity_override=case["input"].get("identity", {}),
            request_id=case["id"],
        )
    except CoreError as exc:
        if expected.get("error_type") == exc.type:
            assertion = {"name": "error_type", "expected": exc.type, "actual": exc.type, "ok": True}
            return _case_result(case, [assertion], status="pass", error={"type": exc.type, "message": exc.message})
        raise

    model = result.subtasks[0]["model"] if result.subtasks else ""
    domain = result.subtasks[0]["domain"] if result.subtasks else ""
    if case.get("track") == "smoke":
        coverage = result.coverage or {}
        metrics = {
            "latency_ms": result.trace["latency_ms"],
            "tokens_in": result.trace["tokens_in"],
            "tokens_out": result.trace["tokens_out"],
            "chars": len(result.response),
        }
        thresholds_met = _thresholds_met(
            metrics,
            case.get("thresholds", {}),
            response=result.response,
            observed={
                "stop_reason": result.stop_reason,
                "coverage_complete": bool(coverage.get("coverage_complete")),
                "chunk_index": int(coverage.get("chunk_index", 0)),
            },
        )
        return _smoke_result(
            case,
            metrics,
            thresholds_met,
            domain=domain,
            model=model,
        )

    coverage = result.coverage or {}
    actual: dict[str, Any] = {
        "stop_reason": result.stop_reason,
        "response": result.response,
        "checkpoints": result.checkpoints,
        "subtasks": _subtask_expectation(result.subtasks, expected.get("subtasks", [])),
        "checkpoint_counts": {
            name: result.checkpoints.count(name) for name in expected.get("checkpoint_counts", {})
        },
        "coverage_complete": coverage.get("coverage_complete"),
        "completed_units": coverage.get("completed_units"),
        "failed_units": coverage.get("failed_units"),
        "pending_units": coverage.get("pending_units"),
        "chunk_index": coverage.get("chunk_index"),
        "units": _subtask_expectation(coverage.get("units", []), expected.get("units", [])),
    }
    for limit in ("max_chunks", "max_total_tokens", "max_time_s"):
        if limit in expected:
            actual[limit] = _effective_limit_actual(result, limit, expected[limit])
    trace_events = _read_trace_events(config)
    subtask_events = [
        event for event in trace_events
        if event.get("event") == "done" and "subtask_index" in event.get("payload", {})
    ]
    fields = expected.get("subtask_trace_fields", {})
    actual["subtask_trace_fields"] = {
        field: subtask_events[0].get(field) if subtask_events else None for field in fields
    }
    actual["subtask_traces_share_task_id"] = bool(subtask_events) and len(
        {event["payload"].get("task_id") for event in subtask_events}
    ) == 1
    actual["subtask_traces_link_parent"] = bool(subtask_events) and all(
        event["payload"].get("parent_request_id") == case["id"] for event in subtask_events
    )
    assertions = _assertions(actual, expected)
    return _case_result(case, assertions, domain=domain, model=model)


def _task_adapters(case: dict[str, Any]) -> dict[str, ScriptedFakeAdapter]:
    script = case.get("world", {}).get("script", {})
    if "units" in script:
        generator_responses = script.get("generator_responses", {})
        generator_finish_reasons = script.get("generator_finish_reasons", {})
        adapters: dict[str, ScriptedFakeAdapter] = {
            model: _FinishReasonScriptedFakeAdapter(
                model,
                [str(response) for response in responses],
                [str(reason) for reason in generator_finish_reasons.get(model, [])],
            )
            for model, responses in generator_responses.items()
        }
        adapters["fake_planner"] = ScriptedFakeAdapter(
            "fake_planner",
            [json.dumps(script["units"], ensure_ascii=False)],
        )
        adapters["fake_validator"] = ScriptedFakeAdapter(
            "fake_validator",
            [
                json.dumps(decision, ensure_ascii=False)
                for decision in script.get("validator_decisions", [])
            ],
        )
        return adapters

    planner_responses: list[str] = []
    decisions = iter(script.get("evaluate_decisions", []))
    for plan in script.get("plans", []):
        planner_responses.append(json.dumps(plan, ensure_ascii=False))
        try:
            planner_responses.append(str(next(decisions)))
        except StopIteration:
            pass
    planner_responses.extend(str(decision) for decision in decisions)
    responses = dict(script.get("responses", {}))
    adapters = {
        model: ScriptedFakeAdapter(model, [str(response)]) for model, response in responses.items()
    }
    adapters["fake_planner"] = ScriptedFakeAdapter("fake_planner", planner_responses)
    return adapters


class _FinishReasonScriptedFakeAdapter(ScriptedFakeAdapter):
    def __init__(
        self,
        model: str,
        responses: list[str],
        finish_reasons: list[str],
    ) -> None:
        super().__init__(model, responses)
        self.finish_reasons = finish_reasons
        self.calls = 0

    def stream(self, req):
        prompt = req.messages[-1]["content"]
        text = self._next_response()
        finish_reason = (
            self.finish_reasons[self.calls]
            if self.calls < len(self.finish_reasons)
            else self.finish_reason
        )
        self.calls += 1
        yield Event("token", {"text": text})
        yield Event(
            "done",
            {
                "text": text,
                "model": self.model,
                "tokens_in": len(prompt.split()) if prompt else 0,
                "tokens_out": len(text.split()) if text else 0,
                "finish_reason": finish_reason,
            },
        )


def _effective_limit_actual(result: Any, name: str, expected: int) -> Any:
    effective = result.params.get(name)
    coverage = result.coverage or {}
    within_limit = True
    if name == "max_chunks":
        within_limit = int(coverage.get("chunk_index", 0)) <= expected
    elif name == "max_total_tokens":
        tokens = int(coverage.get("tokens_in", 0)) + int(coverage.get("tokens_out", 0))
        within_limit = tokens <= expected
    elif name == "max_time_s":
        within_limit = int(result.trace.get("latency_ms", 0)) <= expected * 1000
    if effective == expected and within_limit:
        return expected
    return {"effective": effective, "within_limit": within_limit}


def _subtask_expectation(actual: list[dict[str, Any]], expected: list[dict[str, Any]]) -> list[dict[str, Any]]:
    return [{key: item.get(key) for key in expected_item} for item, expected_item in zip(actual, expected)]


def _read_trace_events(config: Any) -> list[dict[str, Any]]:
    if config.telemetry is None or not config.telemetry.jsonl_path:
        return []
    path = Path(config.telemetry.jsonl_path)
    if not path.exists():
        return []
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines()]


def _execute_model_list(case: dict[str, Any], *, config_path: str | Path | None) -> dict[str, Any]:
    config = _case_config(case, config_path=config_path)
    registry = ModelRegistry(config, availability=_case_availability(case))
    records = registry.model_records()
    assertions = _assertions({"status": "ok"}, case.get("expect", {}))
    return _case_result(case, assertions, domain="", model=records[0]["id"] if records else "")


def _execute_config_validate(case: dict[str, Any]) -> dict[str, Any]:
    raw = case["input"].get("config_inline", {})
    expected = case.get("expect", {})
    try:
        validate_config_dict(raw)
    except CoreError as exc:
        actual = {"error_type": exc.type, "error_field": exc.field}
        assertions = _assertions(actual, expected)
        return _case_result(
            case,
            assertions,
            status="pass" if all(item["ok"] for item in assertions) else "fail",
            error={"type": exc.type, "message": exc.message},
        )
    config = load_config_from_dict(raw)
    assertions = _assertions({"status": "ok", "models": len(config.models)}, expected)
    return _case_result(case, assertions)


def _case_config(case: dict[str, Any], *, config_path: str | Path | None):
    if "config_inline" in case.get("input", {}):
        return load_config_from_dict(case["input"]["config_inline"])
    fixture = case.get("fixture")
    if not fixture and config_path is None:
        return load_config_from_dict(case["input"].get("config_inline", {}))
    config = load_config(fixture or config_path)
    tmp_path = Path(tempfile.mkdtemp(prefix="ianest_eval_"))
    csv_path = tmp_path / f"{case['id']}.csv"
    jsonl_path = tmp_path / f"{case['id']}.jsonl"
    config = replace(
        config,
        telemetry=TelemetryConfig(csv_path=str(csv_path), jsonl_path=str(jsonl_path), strict_mode=False),
    )
    return config


def _case_availability(case: dict[str, Any]) -> StaticAvailabilityProvider:
    unavailable = set(case.get("world", {}).get("unavailable_models", []))
    return StaticAvailabilityProvider(unavailable_models=unavailable)


def _case_reasoning_responses(case: dict[str, Any]) -> list[str]:
    responses = case.get("world", {}).get("reasoning_responses", [])
    return [json.dumps(item, ensure_ascii=False) if isinstance(item, dict) else str(item) for item in responses]


def _assertions(actual: dict[str, Any], expected: dict[str, Any]) -> list[dict[str, Any]]:
    assertions = []
    for name, expected_value in expected.items():
        if name == "trace_fields":
            continue
        actual_value = actual.get(name)
        assertions.append(
            {
                "name": name,
                "expected": expected_value,
                "actual": actual_value,
                "ok": actual_value == expected_value,
            }
        )
    return assertions


def _case_result(
    case: dict[str, Any],
    assertions: list[dict[str, Any]],
    *,
    domain: str = "",
    model: str = "",
    status: str | None = None,
    error: dict[str, str] | None = None,
) -> dict[str, Any]:
    result = {
        "case_id": case["id"],
        "track": case.get("track", ""),
        "status": status or ("pass" if all(item["ok"] for item in assertions) else "fail"),
        "capability": case.get("capability", ""),
        "domain": domain,
        "model": model,
        "latency_ms": 0,
        "assertions": assertions,
    }
    if error is not None:
        result["error"] = error
    return result


def _smoke_result(
    case: dict[str, Any],
    metrics: dict[str, Any],
    thresholds_met: bool,
    *,
    domain: str,
    model: str,
) -> dict[str, Any]:
    return {
        "case_id": case["id"],
        "track": case.get("track", ""),
        "status": "pass" if thresholds_met else "fail",
        "capability": case.get("capability", ""),
        "domain": domain,
        "model": model,
        "latency_ms": metrics["latency_ms"],
        "metrics": metrics,
        "thresholds_met": thresholds_met,
    }


def _case_error(case: dict[str, Any], started: float, exc: CoreError) -> dict[str, Any]:
    return {
        "case_id": case["id"],
        "track": case.get("track", ""),
        "status": "error",
        "capability": case.get("capability", ""),
        "domain": "",
        "model": "",
        "latency_ms": _latency_ms(started),
        "assertions": [],
        "error": {"type": exc.type, "message": exc.message},
    }


def _totals(results: list[dict[str, Any]]) -> dict[str, dict[str, int]]:
    totals = {"conformance": {"pass": 0, "fail": 0}, "smoke": {"pass": 0, "fail": 0}}
    for result in results:
        track = result["track"]
        if track not in totals:
            continue
        key = "pass" if result["status"] == "pass" else "fail"
        totals[track][key] += 1
    return totals


def _thresholds_met(
    metrics: dict[str, Any],
    thresholds: dict[str, Any],
    *,
    response: str = "",
    observed: dict[str, Any] | None = None,
) -> bool:
    values = {**metrics, **(observed or {})}
    if "latency_ms_max" in thresholds and metrics["latency_ms"] > thresholds["latency_ms_max"]:
        return False
    if thresholds.get("must_be_nonempty") and metrics["chars"] == 0:
        return False
    if "min_chars" in thresholds and metrics["chars"] < thresholds["min_chars"]:
        return False
    if "must_contain" in thresholds and not all(
        text in response for text in thresholds["must_contain"]
    ):
        return False
    if "stop_reason" in thresholds and values.get("stop_reason") != thresholds["stop_reason"]:
        return False
    if (
        "coverage_complete" in thresholds
        and values.get("coverage_complete") is not thresholds["coverage_complete"]
    ):
        return False
    if "chunk_index_min" in thresholds and values.get("chunk_index", 0) < thresholds["chunk_index_min"]:
        return False
    return True


def _conformance_digest(results: list[dict[str, Any]]) -> str:
    deterministic = []
    for result in results:
        if result["track"] != "conformance":
            continue
        deterministic.append(
            {
                "case_id": result["case_id"],
                "status": result["status"],
                "capability": result["capability"],
                "domain": result["domain"],
                "model": result["model"],
                "assertions": result.get("assertions", []),
                "error": result.get("error"),
            }
        )
    payload = json.dumps(deterministic, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()


def _verdict_pass(results: list[dict[str, Any]], totals: dict[str, dict[str, int]]) -> bool:
    if totals["conformance"]["fail"] != 0:
        return False
    return all(result["status"] == "pass" for result in results)


def _latency_ms(started: float) -> int:
    return int((time.monotonic() - started) * 1000)
