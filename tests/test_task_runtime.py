from __future__ import annotations

import csv
import json
from dataclasses import replace

import pytest

from ianest_core.adapters import ScriptedFakeAdapter
from ianest_core.config import load_config
from ianest_core.config.schema import TelemetryConfig
from ianest_core.errors import CoreError, ModelUnavailable
from ianest_core.registry import StaticAvailabilityProvider
from ianest_core.runtime import TaskRuntime
from ianest_core.runtime.task_runtime import _parse_evaluation_decision, _parse_plan


def test_plan_parser_accepts_markdown_fences() -> None:
    assert _parse_plan('```json\n[{"prompt": "s1"}]\n```') == [{"prompt": "s1"}]


def test_plan_parser_accepts_surrounding_prose() -> None:
    assert _parse_plan('Este es el plan: [{"prompt": "s1"}] Espero que ayude.') == [{"prompt": "s1"}]


def test_evaluation_parser_accepts_punctuation() -> None:
    assert _parse_evaluation_decision("done.") == "done"


def test_evaluation_parser_accepts_surrounding_prose() -> None:
    assert _parse_evaluation_decision("La respuesta es: done") == "done"


def test_domain_hint_is_advisory_context_for_router(tmp_path) -> None:
    config = replace(
        load_config("eval/fixtures/router.yaml"),
        telemetry=TelemetryConfig(
            csv_path=str(tmp_path / "trace.csv"),
            jsonl_path=str(tmp_path / "trace.jsonl"),
        ),
    )
    router_adapter = CountingScriptedAdapter(
        "fake_router",
        ['{"domain": "codigo", "confidence": 0.9, "reason": "codigo"}'],
    )
    adapters = {
        "fake_router": router_adapter,
        "fake_planner": ScriptedFakeAdapter(
            "fake_planner", [json.dumps([{"prompt": "escribe una funcion", "domain_hint": "Filosofia"}]), "done"]
        ),
        "fake_code": ScriptedFakeAdapter("fake_code", ["FUNCION"]),
        "fake_combiner": ScriptedFakeAdapter("fake_combiner", ["FINAL"]),
    }
    result = TaskRuntime(config, adapter_factory=adapters.get).run(prompt="tarea", request_id="parent")

    assert result.subtasks[0]["domain"] == "codigo"
    assert "domain_hint_ignored" not in result.subtasks[0]
    assert router_adapter.calls == 1
    assert 'domain_hint="Filosofia"' in router_adapter.prompts[0]
    events = [json.loads(line) for line in (tmp_path / "trace.jsonl").read_text().splitlines()]
    subtask_done = next(
        event for event in events
        if event["event"] == "done" and event["payload"].get("subtask_index") == 0
    )
    assert "domain_hint_ignored" not in subtask_done["payload"]


def test_subtask_declared_domain_bypasses_router(tmp_path) -> None:
    config = replace(
        load_config("eval/fixtures/router.yaml"),
        telemetry=TelemetryConfig(
            csv_path=str(tmp_path / "trace.csv"),
            jsonl_path=str(tmp_path / "trace.jsonl"),
        ),
    )
    router_adapter = CountingScriptedAdapter("fake_router", [])
    adapters = {
        "fake_router": router_adapter,
        "fake_planner": ScriptedFakeAdapter(
            "fake_planner",
            [json.dumps([{"prompt": "escribe una funcion", "domain": "codigo"}]), "done"],
        ),
        "fake_code": ScriptedFakeAdapter("fake_code", ["FUNCION"]),
        "fake_combiner": ScriptedFakeAdapter("fake_combiner", ["FINAL"]),
    }

    result = TaskRuntime(config, adapter_factory=adapters.get).run(
        prompt="tarea",
        request_id="parent",
    )

    assert result.subtasks[0]["domain"] == "codigo"
    assert result.subtasks[0]["model"] == "fake_code"
    assert router_adapter.calls == 0


def test_task_runtime_runs_plan_fanout_combine_and_evaluate(tmp_path) -> None:
    config = _config(tmp_path)
    adapters = {
        "fake_planner": ScriptedFakeAdapter(
            "fake_planner",
            [json.dumps([{"prompt": "razona", "domain": "razonamiento"}, {"prompt": "codifica", "domain": "codigo"}]), "done"],
        ),
        "fake_reason": ScriptedFakeAdapter("fake_reason", ["A"]),
        "fake_code": ScriptedFakeAdapter("fake_code", ["B"], finish_reason="length"),
        "fake_combiner": ScriptedFakeAdapter("fake_combiner", ["AB"]),
    }
    runtime = TaskRuntime(config, adapter_factory=adapters.get)

    result = runtime.run(
        prompt="tarea",
        identity_override={"user_id": "u42", "service": "local_cli", "session_id": "s7"},
        request_id="parent",
    )

    assert result.response == "AB"
    assert result.stop_reason == "task_done"
    assert result.checkpoints == [
        "task_received", "plan_ready", "subtask_done", "subtask_done",
        "combine_ready", "iteration_end", "task_done",
    ]
    assert [(item["domain"], item["model"]) for item in result.subtasks] == [
        ("razonamiento", "fake_reason"), ("codigo", "fake_code")
    ]
    assert [item["finish_reason"] for item in result.subtasks] == ["stop", "length"]
    assert [item["iteration"] for item in result.subtasks] == [1, 1]
    events = [json.loads(line) for line in (tmp_path / "trace.jsonl").read_text().splitlines()]
    subtask_done = [event for event in events if event["event"] == "done" and event["payload"].get("subtask_index") is not None]
    assert len(subtask_done) == 2
    assert {event["payload"]["task_id"] for event in subtask_done} == {result.trace["task_id"]}
    assert {event["payload"]["parent_request_id"] for event in subtask_done} == {"parent"}
    assert {event["session_id"] for event in subtask_done} == {"s7"}
    code_done = next(event for event in subtask_done if event["payload"].get("subtask_index") == 1)
    assert code_done["payload"]["finish_reason"] == "length"
    assert {event["payload"]["iteration"] for event in subtask_done} == {1}


def test_task_runtime_rerun_records_unique_iteration_and_index_pairs(tmp_path) -> None:
    config = _config(tmp_path)
    adapters = {
        "fake_planner": ScriptedFakeAdapter(
            "fake_planner",
            [json.dumps([{"prompt": "primera", "domain": "general"}, {"prompt": "segunda", "domain": "general"}]), "rerun", "done"],
        ),
        "fake_general": ScriptedFakeAdapter("fake_general", ["A"]),
        "fake_combiner": ScriptedFakeAdapter("fake_combiner", ["AB"]),
    }

    result = TaskRuntime(config, adapter_factory=adapters.get).run(prompt="tarea", request_id="parent")

    assert [(item["iteration"], item["index"]) for item in result.subtasks] == [
        (1, 0), (1, 1), (2, 0), (2, 1),
    ]
    assert len({(item["iteration"], item["index"]) for item in result.subtasks}) == len(result.subtasks)
    events = [json.loads(line) for line in (tmp_path / "trace.jsonl").read_text().splitlines()]
    subtask_done = [
        event for event in events
        if event["event"] == "done" and "subtask_index" in event["payload"]
    ]
    assert {
        (event["payload"]["iteration"], event["payload"]["subtask_index"])
        for event in subtask_done
    } == {
        (1, 0), (1, 1), (2, 0), (2, 1),
    }


def test_task_runtime_requires_orchestration_config() -> None:
    with pytest.raises(CoreError) as exc:
        TaskRuntime(load_config("eval/fixtures/config.yaml"))

    assert exc.value.type == "ConfigError"
    assert exc.value.field == "orchestration"


def test_task_runtime_propagates_subtask_model_unavailable(tmp_path) -> None:
    config = _config(tmp_path)
    planner = ScriptedFakeAdapter("fake_planner", [json.dumps([{"prompt": "razona", "domain": "razonamiento"}])])
    runtime = TaskRuntime(
        config,
        availability=StaticAvailabilityProvider(unavailable_models={"fake_reason"}),
        adapter_factory={"fake_planner": planner}.get,
    )

    with pytest.raises(ModelUnavailable):
        runtime.run(prompt="imposible")


def test_task_runtime_limits_real_accumulated_tokens_and_traces_them(tmp_path) -> None:
    config = replace(
        _config(tmp_path),
        orchestration=replace(_config(tmp_path).orchestration, max_context_tokens=1),
    )
    adapters = {
        "fake_planner": ScriptedFakeAdapter("fake_planner", [json.dumps([{"prompt": "subtarea", "domain": "general"}]), "rerun"]),
        "fake_general": ScriptedFakeAdapter("fake_general", ["respuesta de subtarea"]),
        "fake_combiner": ScriptedFakeAdapter("fake_combiner", ["respuesta combinada"]),
    }

    result = TaskRuntime(config, adapter_factory=adapters.get).run(prompt="tarea", request_id="parent")

    with (tmp_path / "trace.csv").open(newline="") as trace_file:
        prompt_events = [
            event for event in csv.DictReader(trace_file, delimiter=";")
            if event["capability"] == "prompt.run" and event["event"] == "done"
        ]
    assert result.stop_reason == "max_context_tokens"
    assert result.trace["tokens_in"] == sum(int(event["tokens_in"]) for event in prompt_events)
    assert result.trace["tokens_out"] == sum(int(event["tokens_out"]) for event in prompt_events)
    assert result.trace["tokens_in"] + result.trace["tokens_out"] > config.orchestration.max_context_tokens


def test_task_runtime_done_beats_exceeded_context_budget(tmp_path) -> None:
    config = replace(
        _config(tmp_path),
        orchestration=replace(_config(tmp_path).orchestration, max_context_tokens=1),
    )
    adapters = {
        "fake_planner": ScriptedFakeAdapter("fake_planner", [json.dumps([{"prompt": "subtarea", "domain": "general"}]), "done"]),
        "fake_general": ScriptedFakeAdapter("fake_general", ["respuesta de subtarea"]),
        "fake_combiner": ScriptedFakeAdapter("fake_combiner", ["respuesta combinada"]),
    }

    result = TaskRuntime(config, adapter_factory=adapters.get).run(prompt="tarea", request_id="parent")

    assert result.stop_reason == "task_done"
    assert result.trace["tokens_in"] + result.trace["tokens_out"] > config.orchestration.max_context_tokens


def test_task_runtime_done_beats_exceeded_time_limit(tmp_path) -> None:
    config = _config(tmp_path)
    adapters = {
        "fake_planner": ScriptedFakeAdapter("fake_planner", [json.dumps([{"prompt": "subtarea", "domain": "general"}]), "done"]),
        "fake_general": ScriptedFakeAdapter("fake_general", ["respuesta de subtarea"]),
        "fake_combiner": ScriptedFakeAdapter("fake_combiner", ["respuesta combinada"]),
    }

    result = TaskRuntime(
        config,
        adapter_factory=adapters.get,
        simulated={"elapsed_s": config.orchestration.max_time_s + 1},
    ).run(prompt="tarea", request_id="parent")

    assert result.stop_reason == "task_done"


def test_task_runtime_simulated_context_tokens_override_real_accumulation(tmp_path) -> None:
    config = replace(
        _config(tmp_path),
        orchestration=replace(_config(tmp_path).orchestration, max_context_tokens=1),
    )
    adapters = {
        "fake_planner": ScriptedFakeAdapter("fake_planner", [json.dumps([{"prompt": "subtarea", "domain": "general"}]), "done"]),
        "fake_general": ScriptedFakeAdapter("fake_general", ["respuesta de subtarea"]),
        "fake_combiner": ScriptedFakeAdapter("fake_combiner", ["respuesta combinada"]),
    }

    result = TaskRuntime(
        config, adapter_factory=adapters.get, simulated={"context_tokens": 0}
    ).run(prompt="tarea", request_id="parent")

    assert result.stop_reason == "task_done"
    assert result.trace["tokens_in"] + result.trace["tokens_out"] > config.orchestration.max_context_tokens


def _config(tmp_path):
    return replace(
        load_config("eval/fixtures/orchestration.yaml"),
        telemetry=TelemetryConfig(csv_path=str(tmp_path / "trace.csv"), jsonl_path=str(tmp_path / "trace.jsonl")),
    )


class CountingScriptedAdapter(ScriptedFakeAdapter):
    def __init__(self, model: str, responses: list[str]) -> None:
        super().__init__(model, responses)
        self.calls = 0
        self.prompts: list[str] = []

    def stream(self, req):
        self.calls += 1
        self.prompts.append(req.messages[-1]["content"])
        yield from super().stream(req)
