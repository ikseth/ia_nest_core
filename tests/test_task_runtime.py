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


def _plan_response(subtasks) -> str:
    requirement_id = "r1"
    return json.dumps({
        "requirements": [{"id": requirement_id, "text": "complete the task"}],
        "subtasks": [
            {**subtask, "covers": subtask.get("covers", [requirement_id])}
            for subtask in subtasks
        ],
    })


def test_plan_parser_accepts_markdown_fences() -> None:
    assert _parse_plan('```json\n[{"prompt": "s1"}]\n```') == [{"prompt": "s1"}]


def test_plan_parser_accepts_surrounding_prose() -> None:
    assert _parse_plan('Este es el plan: [{"prompt": "s1"}] Espero que ayude.') == [{"prompt": "s1"}]


def test_evaluation_parser_accepts_punctuation() -> None:
    assert _parse_evaluation_decision("done.") == "done"


def test_evaluation_parser_accepts_surrounding_prose() -> None:
    assert _parse_evaluation_decision("La respuesta es: done") == "done"


@pytest.mark.parametrize("depends_on", [[1], ["1"], "1"])
def test_pipeline_accepts_integer_and_numeric_string_dependencies(tmp_path, depends_on) -> None:
    planner = CountingScriptedAdapter(
        "fake_planner",
        [_plan_response([{"prompt": "first", "domain": "general", "depends_on": depends_on}, {"prompt": "second", "domain": "general"}]), "done"],
    )
    general = CountingScriptedAdapter("fake_general", ["SECOND", "FIRST"])
    adapters = {
        "fake_planner": planner,
        "fake_general": general,
        "fake_combiner": ScriptedFakeAdapter("fake_combiner", ["FINAL"]),
    }

    result = TaskRuntime(_config(tmp_path), adapter_factory=adapters.get).run(prompt="task", request_id="parent")

    assert result.response == "FINAL"
    assert [item["response"] for item in result.subtasks] == ["FIRST", "SECOND"]
    assert general.calls == 2
    assert "zero-based integer indexes into this same list" in planner.prompts[0]


def test_pipeline_rejects_non_numeric_dependency_string(tmp_path) -> None:
    planner = CountingScriptedAdapter(
        "fake_planner", [_plan_response([{"prompt": "subtask", "domain": "general", "depends_on": ["a"]}])]
    )
    with pytest.raises(CoreError) as exc:
        TaskRuntime(_config(tmp_path), adapter_factory={"fake_planner": planner}.get).run(prompt="task", request_id="parent")

    assert exc.value.type == "PlanDependencyError"
    assert exc.value.field == "depends_on"


def test_pipeline_rejects_boolean_dependency(tmp_path) -> None:
    planner = CountingScriptedAdapter(
        "fake_planner",
        [_plan_response([
            {"prompt": "first", "domain": "general", "depends_on": [True]},
            {"prompt": "second", "domain": "general"},
        ])],
    )
    general = CountingScriptedAdapter("fake_general", [])
    adapters = {"fake_planner": planner, "fake_general": general}
    with pytest.raises(CoreError) as exc:
        TaskRuntime(_config(tmp_path), adapter_factory=adapters.get).run(prompt="task", request_id="parent")

    assert exc.value.type == "PlanDependencyError"
    assert exc.value.field == "depends_on"
    assert general.calls == 0


def test_pipeline_rejects_out_of_range_dependency_before_subtasks_run(tmp_path) -> None:
    planner = CountingScriptedAdapter(
        "fake_planner", [_plan_response([{"prompt": "subtask", "domain": "general", "depends_on": [1]}])]
    )
    general = CountingScriptedAdapter("fake_general", [])
    adapters = {"fake_planner": planner, "fake_general": general}

    with pytest.raises(CoreError, match="valid indexes") as exc:
        TaskRuntime(_config(tmp_path), adapter_factory=adapters.get).run(prompt="task", request_id="parent")

    assert exc.value.type == "PlanDependencyError"
    assert exc.value.field == "depends_on"
    assert general.calls == 0


def test_pipeline_rejects_cyclic_dependencies_before_subtasks_run(tmp_path) -> None:
    planner = CountingScriptedAdapter(
        "fake_planner",
        [_plan_response([
            {"prompt": "first", "domain": "general", "depends_on": [1]},
            {"prompt": "second", "domain": "general", "depends_on": [0]},
        ])],
    )
    general = CountingScriptedAdapter("fake_general", [])
    adapters = {"fake_planner": planner, "fake_general": general}

    with pytest.raises(CoreError, match="cycle") as exc:
        TaskRuntime(_config(tmp_path), adapter_factory=adapters.get).run(prompt="task", request_id="parent")

    assert exc.value.type == "PlanDependencyError"
    assert exc.value.field == "depends_on"
    assert general.calls == 0


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
            "fake_planner", [_plan_response([{"prompt": "escribe una funcion", "domain_hint": "Filosofia"}]), "done"]
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
            [_plan_response([{"prompt": "escribe una funcion", "domain": "codigo"}]), "done"],
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


def test_pipeline_subtask_prompt_keeps_objective_as_context_and_routing_bare(tmp_path) -> None:
    objective = "Explain the legend of the number 47 in cinema"
    subtask = "Find films that mention the number"
    config = replace(
        load_config("eval/fixtures/router.yaml"),
        telemetry=TelemetryConfig(
            csv_path=str(tmp_path / "trace.csv"),
            jsonl_path=str(tmp_path / "trace.jsonl"),
        ),
    )
    router_adapter = CountingScriptedAdapter(
        "fake_router",
        ['{"domain": "codigo", "confidence": 0.9, "reason": "films"}'],
    )
    subtask_adapter = CountingScriptedAdapter("fake_code", ["FILMS"])
    combiner_adapter = CountingScriptedAdapter("fake_combiner", ["FINAL"])
    adapters = {
        "fake_router": router_adapter,
        "fake_planner": ScriptedFakeAdapter(
            "fake_planner", [_plan_response([{"prompt": subtask}]), "done"]
        ),
        "fake_code": subtask_adapter,
        "fake_combiner": combiner_adapter,
    }

    result = TaskRuntime(config, adapter_factory=adapters.get).run(prompt=objective, request_id="parent")

    execution_prompt = subtask_adapter.prompts[0]
    assert "Global objective (CONTEXT ONLY; do not answer it as a whole):" in execution_prompt
    assert objective in execution_prompt
    assert "Assigned subtask (the ONLY content to produce):" in execution_prompt
    assert subtask in execution_prompt
    assert "Do not address other subtasks or any other part of the global objective." in execution_prompt
    assert objective not in router_adapter.prompts[0]
    assert subtask in router_adapter.prompts[0]
    assert result.subtasks[0]["prompt"] == subtask
    assert "internally consistent answer" in combiner_adapter.prompts[0]
    assert "present them as divergent versions" in combiner_adapter.prompts[0]
    assert "Do not decide which version is true or verify any claim." in combiner_adapter.prompts[0]
    assert "Do not add qualifications where the results do not diverge." in combiner_adapter.prompts[0]


def test_coverage_generation_and_validation_prompts_remain_unchanged(tmp_path) -> None:
    objective = "Cover the first film"
    unit = {"id": "u1", "prompt": "describe the first film", "domain": "general"}
    config = replace(
        load_config("eval/fixtures/orchestration_coverage.yaml"),
        telemetry=TelemetryConfig(
            csv_path=str(tmp_path / "trace.csv"),
            jsonl_path=str(tmp_path / "trace.jsonl"),
        ),
    )
    generator = CountingScriptedAdapter("fake_general", ["FILM"])
    validator = CountingScriptedAdapter("fake_validator", ['["u1"]'])
    derivation = json.dumps({
        "requirements": [{"id": "r1", "text": "complete the task"}],
        "units": [{**unit, "covers": ["r1"]}],
    })
    adapters = {
        "fake_planner": ScriptedFakeAdapter("fake_planner", [derivation]),
        "fake_general": generator,
        "fake_validator": validator,
    }

    TaskRuntime(config, adapter_factory=adapters.get).run(prompt=objective, mode="coverage")

    assert generator.prompts == [
        "Global objective (CONTEXT ONLY; do not answer it as a whole): Cover the first film\n"
        'Assigned coverage units (the ONLY content to produce): [{"id": "u1", "prompt": "describe the first film"}]\n'
        "Completed unit references: none\n"
        "Produce ONLY the content that directly fulfills the assigned coverage units. "
        "Do not include a preamble, conclusion, transition, or meta-commentary. "
        "Do not restate or rephrase a unit prompt as an introductory sentence; "
        "emit the requested content directly. "
        "Do not address unassigned units or any other part of the global objective. "
        "Do not repeat completed units."
    ]
    assert validator.prompts == [
        "You decide which target units a fragment covers. Return ONLY a JSON array of "
        "ids, taken exactly from this list and nothing else: [\"u1\"]. Include an id if and only if the "
        "fragment addresses that unit. Do not include titles, content, explanations or "
        "any other text; the answer must be short. Example of a valid answer: [\"u1\"].\n"
        "Objective: Cover the first film\n"
        "Target units: [{\"id\": \"u1\", \"prompt\": \"describe the first film\"}]\n"
        "Fragment: FILM"
    ]


def test_task_runtime_runs_plan_fanout_combine_and_evaluate(tmp_path) -> None:
    config = _config(tmp_path)
    adapters = {
        "fake_planner": ScriptedFakeAdapter(
            "fake_planner",
            [_plan_response([{"prompt": "razona", "domain": "razonamiento"}, {"prompt": "codifica", "domain": "codigo"}]), "done"],
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
            [_plan_response([{"prompt": "primera", "domain": "general"}, {"prompt": "segunda", "domain": "general"}]), "rerun", "done"],
        ),
        "fake_general": ScriptedFakeAdapter("fake_general", ["A"]),
        "fake_combiner": ScriptedFakeAdapter("fake_combiner", ["AB"]),
    }

    result = TaskRuntime(config, adapter_factory=adapters.get).run(prompt="tarea", request_id="parent")

    assert [(item["iteration"], item["index"]) for item in result.subtasks] == [
        (1, 0), (1, 1), (2, 0), (2, 1),
    ]
    assert len({(item["iteration"], item["index"]) for item in result.subtasks}) == len(result.subtasks)
    assert result.checkpoints.count("plan_ready") == 1
    assert result.checkpoints.count("iteration_end") == 2
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
    planner = ScriptedFakeAdapter("fake_planner", [_plan_response([{"prompt": "razona", "domain": "razonamiento"}])])
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
        "fake_planner": ScriptedFakeAdapter("fake_planner", [_plan_response([{"prompt": "subtarea", "domain": "general"}]), "rerun"]),
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
        "fake_planner": ScriptedFakeAdapter("fake_planner", [_plan_response([{"prompt": "subtarea", "domain": "general"}]), "done"]),
        "fake_general": ScriptedFakeAdapter("fake_general", ["respuesta de subtarea"]),
        "fake_combiner": ScriptedFakeAdapter("fake_combiner", ["respuesta combinada"]),
    }

    result = TaskRuntime(config, adapter_factory=adapters.get).run(prompt="tarea", request_id="parent")

    assert result.stop_reason == "task_done"
    assert result.trace["tokens_in"] + result.trace["tokens_out"] > config.orchestration.max_context_tokens


def test_task_runtime_done_beats_exceeded_time_limit(tmp_path) -> None:
    config = _config(tmp_path)
    adapters = {
        "fake_planner": ScriptedFakeAdapter("fake_planner", [_plan_response([{"prompt": "subtarea", "domain": "general"}]), "done"]),
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
        "fake_planner": ScriptedFakeAdapter("fake_planner", [_plan_response([{"prompt": "subtarea", "domain": "general"}]), "done"]),
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
