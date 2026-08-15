from __future__ import annotations

import json

from ianest_core.adapters import Event, ScriptedFakeAdapter
from ianest_core.adapters.base import ModelRequest
from ianest_core.config import load_config
from ianest_core.runtime import TaskRuntime


class _ForbiddenAdapter:
    def stream(self, _request: ModelRequest):
        raise AssertionError("unexpected model invocation")
        yield Event("done", {})


class _EvaluationOnlyAdapter(ScriptedFakeAdapter):
    def __init__(self) -> None:
        super().__init__("fake_planner", ["done"])
        self.prompts: list[str] = []

    def stream(self, request: ModelRequest):
        prompt = request.messages[-1]["content"]
        self.prompts.append(prompt)
        assert "Evaluate the combined answer" in prompt
        yield from super().stream(request)


def test_task_plan_does_not_execute_subtasks_combine_or_evaluate() -> None:
    planner = ScriptedFakeAdapter(
        "fake_planner",
        [
            json.dumps(
                {
                    "requirements": [{"id": "r1", "text": "analizar"}],
                    "subtasks": [
                        {"prompt": "analiza", "domain": "razonamiento", "covers": ["r1"]}
                    ],
                }
            )
        ],
    )
    runtime = TaskRuntime(
        load_config("eval/fixtures/orchestration_effort.yaml"),
        adapter_factory=lambda model: planner if model == "fake_planner" else _ForbiddenAdapter(),
    )

    result = runtime.plan(prompt="analiza una cosa", request_id="task-plan")

    assert result.plan == [
        {"index": 0, "prompt": "analiza", "domain": "razonamiento", "depends_on": []}
    ]
    assert planner.index == 1


def test_supplied_plan_does_not_call_planner_for_plan_stage() -> None:
    evaluator = _EvaluationOnlyAdapter()
    adapters = {
        "fake_planner": evaluator,
        "fake_general": ScriptedFakeAdapter("fake_general", ["PARTE"]),
        "fake_combiner": ScriptedFakeAdapter("fake_combiner", ["FINAL"]),
    }
    runtime = TaskRuntime(
        load_config("eval/fixtures/orchestration_effort.yaml"),
        adapter_factory=adapters.get,
    )

    result = runtime.run(
        prompt="explica una cosa",
        plan=[{"index": 0, "prompt": "explica", "domain": "general", "depends_on": []}],
        requirements=[{"id": "r1", "statement": "explicar", "covered_by": [0]}],
        request_id="supplied-plan",
    )

    assert result.stop_reason == "task_done"
    assert result.plan_attempts == 0
    assert len(evaluator.prompts) == 1
