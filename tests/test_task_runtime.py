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


def test_task_runtime_runs_plan_fanout_combine_and_evaluate(tmp_path) -> None:
    config = _config(tmp_path)
    adapters = {
        "fake_planner": ScriptedFakeAdapter(
            "fake_planner",
            [json.dumps([{"prompt": "razona", "domain_hint": "razonamiento"}, {"prompt": "codifica", "domain_hint": "codigo"}]), "done"],
        ),
        "fake_reason": ScriptedFakeAdapter("fake_reason", ["A"]),
        "fake_code": ScriptedFakeAdapter("fake_code", ["B"]),
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
    events = [json.loads(line) for line in (tmp_path / "trace.jsonl").read_text().splitlines()]
    subtask_done = [event for event in events if event["event"] == "done" and event["payload"].get("subtask_index") is not None]
    assert len(subtask_done) == 2
    assert {event["payload"]["task_id"] for event in subtask_done} == {result.trace["task_id"]}
    assert {event["payload"]["parent_request_id"] for event in subtask_done} == {"parent"}
    assert {event["session_id"] for event in subtask_done} == {"s7"}


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
