from __future__ import annotations

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


def test_domain_hint_normalizes_case_and_accents(tmp_path) -> None:
    runtime = TaskRuntime(_config(tmp_path))

    assert runtime._resolve_domain_hint("  RAZONAMIÉNTO ") == "razonamiento"


def test_unknown_domain_hint_is_ignored_and_routed(tmp_path) -> None:
    config = _config(tmp_path)
    adapters = {
        "fake_planner": ScriptedFakeAdapter(
            "fake_planner", [json.dumps([{"prompt": "escribe una funcion", "domain_hint": "inventado"}]), "done"]
        ),
        "fake_code": ScriptedFakeAdapter("fake_code", ["FUNCION"]),
        "fake_combiner": ScriptedFakeAdapter("fake_combiner", ["FINAL"]),
    }
    result = TaskRuntime(config, adapter_factory=adapters.get).run(prompt="tarea", request_id="parent")

    assert result.subtasks[0]["domain"] == "codigo"
    assert result.subtasks[0]["domain_hint_ignored"] == "inventado"
    events = [json.loads(line) for line in (tmp_path / "trace.jsonl").read_text().splitlines()]
    subtask_done = next(
        event for event in events
        if event["event"] == "done" and event["payload"].get("subtask_index") == 0
    )
    assert subtask_done["payload"]["domain_hint_ignored"] == "inventado"


def test_task_runtime_runs_plan_fanout_combine_and_evaluate(tmp_path) -> None:
    config = _config(tmp_path)
    adapters = {
        "fake_planner": ScriptedFakeAdapter(
            "fake_planner",
            [json.dumps([{"prompt": "razona", "domain_hint": "razonamiento"}, {"prompt": "codifica", "domain_hint": "codigo"}]), "done"],
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
    events = [json.loads(line) for line in (tmp_path / "trace.jsonl").read_text().splitlines()]
    subtask_done = [event for event in events if event["event"] == "done" and event["payload"].get("subtask_index") is not None]
    assert len(subtask_done) == 2
    assert {event["payload"]["task_id"] for event in subtask_done} == {result.trace["task_id"]}
    assert {event["payload"]["parent_request_id"] for event in subtask_done} == {"parent"}
    assert {event["session_id"] for event in subtask_done} == {"s7"}
    code_done = next(event for event in subtask_done if event["payload"].get("subtask_index") == 1)
    assert code_done["payload"]["finish_reason"] == "length"


def test_task_runtime_requires_orchestration_config() -> None:
    with pytest.raises(CoreError) as exc:
        TaskRuntime(load_config("eval/fixtures/config.yaml"))

    assert exc.value.type == "ConfigError"
    assert exc.value.field == "orchestration"


def test_task_runtime_propagates_subtask_model_unavailable(tmp_path) -> None:
    config = _config(tmp_path)
    planner = ScriptedFakeAdapter("fake_planner", [json.dumps([{"prompt": "razona", "domain_hint": "razonamiento"}])])
    runtime = TaskRuntime(
        config,
        availability=StaticAvailabilityProvider(unavailable_models={"fake_reason"}),
        adapter_factory={"fake_planner": planner}.get,
    )

    with pytest.raises(ModelUnavailable):
        runtime.run(prompt="imposible")


def _config(tmp_path):
    return replace(
        load_config("eval/fixtures/orchestration.yaml"),
        telemetry=TelemetryConfig(csv_path=str(tmp_path / "trace.csv"), jsonl_path=str(tmp_path / "trace.jsonl")),
    )
