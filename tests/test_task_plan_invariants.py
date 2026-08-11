from __future__ import annotations

import json
from dataclasses import replace

import pytest

from ianest_core.adapters import ScriptedFakeAdapter
from ianest_core.config import load_config
from ianest_core.config.schema import TelemetryConfig
from ianest_core.runtime import TaskRuntime


class CapturingScriptedAdapter(ScriptedFakeAdapter):
    def __init__(self, model: str, responses: list[str]) -> None:
        super().__init__(model, responses)
        self.prompts: list[str] = []

    def stream(self, req):
        self.prompts.append(req.messages[-1]["content"])
        yield from super().stream(req)


def _config(tmp_path, mode: str):
    fixture = "orchestration_coverage.yaml" if mode == "coverage" else "orchestration.yaml"
    return replace(
        load_config(f"eval/fixtures/{fixture}"),
        telemetry=TelemetryConfig(
            csv_path=str(tmp_path / "trace.csv"),
            jsonl_path=str(tmp_path / "trace.jsonl"),
        ),
    )


def _derivation(mode: str, requirements, plan) -> str:
    key = "units" if mode == "coverage" else "subtasks"
    return json.dumps({"requirements": requirements, key: plan})


def _item(mode: str, prompt: str, covers: list[str], *, index: int = 1) -> dict:
    item = {"prompt": prompt, "domain": "general", "covers": covers}
    if mode == "coverage":
        item["id"] = f"u{index}"
    return item


def _run(tmp_path, mode: str, planner_responses: list[str], *, prompt: str = "original task"):
    planner = CapturingScriptedAdapter(
        "fake_planner",
        planner_responses + ([] if mode == "coverage" else ["done"]),
    )
    adapters = {
        "fake_planner": planner,
        "fake_general": ScriptedFakeAdapter("fake_general", ["PART"]),
        "fake_combiner": ScriptedFakeAdapter("fake_combiner", ["FINAL"]),
    }
    if mode == "coverage":
        adapters["fake_validator"] = ScriptedFakeAdapter(
            "fake_validator",
            [json.dumps(["u1"])],
        )
    result = TaskRuntime(_config(tmp_path, mode), adapter_factory=adapters.get).run(
        prompt=prompt,
        mode=mode,
        request_id=f"{mode}-task",
    )
    return result, planner


def _run_pipeline_evaluation(tmp_path, evaluation_responses: list[str], *, plan_responses=None):
    requirements = [{"id": "r1", "text": "do the work"}]
    derivation = _derivation(
        "pipeline",
        requirements,
        [_item("pipeline", "work", ["r1"])],
    )
    planner = CapturingScriptedAdapter(
        "fake_planner",
        list(plan_responses or [derivation]) + evaluation_responses,
    )
    adapters = {
        "fake_planner": planner,
        "fake_general": ScriptedFakeAdapter("fake_general", ["PART"]),
        "fake_combiner": ScriptedFakeAdapter("fake_combiner", ["FINAL"]),
    }
    result = TaskRuntime(
        _config(tmp_path, "pipeline"),
        adapter_factory=adapters.get,
    ).run(prompt="original task", request_id="evaluation-task")
    return result, planner


def test_requirements_covered_on_first_plan_has_one_attempt(tmp_path) -> None:
    requirements = [{"id": "r1", "text": "do the work"}]
    result, _ = _run(
        tmp_path,
        "pipeline",
        [_derivation("pipeline", requirements, [_item("pipeline", "work", ["r1"])])],
    )

    assert result.plan_attempts == 1
    assert result.requirements_covered is True
    assert result.uncovered_requirements == []
    assert result.degradations == []
    assert result.evaluation_attempts == 1


def test_orphan_requirement_is_corrected_by_second_plan(tmp_path) -> None:
    requirements = [{"id": "r1", "text": "one"}, {"id": "r2", "text": "two"}]
    first = [_item("pipeline", "one", ["r1"])]
    second = [
        _item("pipeline", "one", ["r1"]),
        _item("pipeline", "two", ["r2"], index=2),
    ]
    result, _ = _run(
        tmp_path,
        "pipeline",
        [_derivation("pipeline", requirements, first), _derivation("pipeline", requirements, second)],
    )

    assert result.stop_reason == "task_done"
    assert result.plan_attempts == 2
    assert result.requirements_covered is True


def test_persistent_orphan_continues_and_marks_result(tmp_path) -> None:
    requirements = [{"id": "r1", "text": "one"}, {"id": "r2", "text": "two"}]
    derivation = _derivation(
        "pipeline",
        requirements,
        [_item("pipeline", "one", ["r1"])],
    )
    result, _ = _run(tmp_path, "pipeline", [derivation, derivation])

    assert result.stop_reason == "task_done"
    assert result.requirements_covered is False
    assert result.uncovered_requirements == ["r2"]


def test_oversized_plan_negotiates_explicit_budget_then_fits(tmp_path) -> None:
    requirements = [{"id": "r1", "text": "work"}]
    oversized = [_item("pipeline", f"part {index}", ["r1"], index=index) for index in range(1, 6)]
    compact = [_item("pipeline", "grouped work", ["r1"])]
    result, planner = _run(
        tmp_path,
        "pipeline",
        [
            _derivation("pipeline", requirements, oversized),
            _derivation("pipeline", requirements, compact),
        ],
    )

    assert result.stop_reason == "task_done"
    assert result.plan_attempts == 2
    assert "explicit budget of 4 units" in planner.prompts[1]


def test_oversized_plan_twice_cuts_with_max_subtasks(tmp_path) -> None:
    requirements = [{"id": "r1", "text": "work"}]
    oversized = [_item("pipeline", f"part {index}", ["r1"], index=index) for index in range(1, 6)]
    derivation = _derivation("pipeline", requirements, oversized)
    result, _ = _run(tmp_path, "pipeline", [derivation, derivation])

    assert result.stop_reason == "max_subtasks"
    assert result.response == ""
    assert result.plan_attempts == 2


def test_known_wrapper_is_unwrapped_without_renegotiation(tmp_path) -> None:
    wrapped = json.dumps({
        "requirements": [{"id": "r1", "text": "work"}],
        "steps": [_item("pipeline", "work", ["r1"])],
    })
    result, planner = _run(tmp_path, "pipeline", [wrapped])

    assert result.plan_attempts == 1
    assert len(planner.prompts) == 2  # PLAN plus EVALUATE.
    assert result.degradations == []


def test_single_subtask_object_is_not_tolerated_and_renegotiates(tmp_path) -> None:
    corrected = _derivation(
        "pipeline",
        [{"id": "r1", "text": "all work"}],
        [_item("pipeline", "all work", ["r1"])],
    )
    result, _ = _run(
        tmp_path,
        "pipeline",
        ['{"prompt": "reduced task", "domain": "general"}', corrected],
    )

    assert result.plan_attempts == 2
    assert result.degradations == []


def test_irrecoverable_plan_degrades_to_full_original_prompt(tmp_path) -> None:
    prompt = "complete original task with every requested part"
    malformed = '{"prompt": "reduced task", "domain": "general"}'
    result, _ = _run(tmp_path, "pipeline", [malformed, malformed], prompt=prompt)

    assert result.stop_reason == "task_done"
    assert result.subtasks[0]["prompt"] == prompt
    assert result.degradations == [
        {"stage": "plan", "reason": "unparseable_shape", "action": "single_subtask"}
    ]


def test_multiple_plan_defects_consume_one_renegotiation(tmp_path) -> None:
    requirements = [{"id": "r1", "text": "work"}, {"id": "r2", "text": "justify"}]
    defective = [_item("pipeline", f"part {index}", ["r1"], index=index) for index in range(1, 6)]
    corrected = [
        _item("pipeline", "grouped work", ["r1"]),
        _item("pipeline", "justify", ["r2"], index=2),
    ]
    result, planner = _run(
        tmp_path,
        "pipeline",
        [
            _derivation("pipeline", requirements, defective),
            _derivation("pipeline", requirements, corrected),
        ],
    )

    assert result.plan_attempts == 2
    assert result.requirements_covered is True
    assert "explicit budget of 4 units" in planner.prompts[1]
    assert "r2" in planner.prompts[1]


def test_missing_requirements_renegotiates_then_continues_marked(tmp_path) -> None:
    bare_plan = json.dumps([_item("pipeline", "work", [])])
    result, _ = _run(tmp_path, "pipeline", [bare_plan, bare_plan])

    assert result.stop_reason == "task_done"
    assert result.plan_attempts == 2
    assert result.requirements_covered is False


@pytest.mark.parametrize("mode", ["pipeline", "coverage"])
def test_plan_invariants_use_same_path_in_both_modes(tmp_path, mode) -> None:
    requirements = [{"id": "r1", "text": "one"}, {"id": "r2", "text": "two"}]
    first = [_item(mode, "one", ["r1"])]
    second = [_item(mode, "all", ["r1", "r2"])]
    result, _ = _run(
        tmp_path / mode,
        mode,
        [_derivation(mode, requirements, first), _derivation(mode, requirements, second)],
    )

    assert result.stop_reason == "task_done"
    assert result.plan_attempts == 2
    assert result.requirements_covered is True
    assert result.degradations == []


def test_coverage_irrecoverable_plan_degrades_without_cutting(tmp_path) -> None:
    malformed = '{"prompt": "reduced", "domain": "general"}'
    result, _ = _run(
        tmp_path,
        "coverage",
        [malformed, malformed],
        prompt="full coverage task",
    )

    assert result.stop_reason == "task_done"
    assert result.subtasks[0]["prompt"] == "full coverage task"
    assert result.degradations == [
        {"stage": "plan", "reason": "unparseable_shape", "action": "single_subtask"}
    ]


def test_undecipherable_evaluation_is_corrected_by_renegotiation(tmp_path) -> None:
    result, planner = _run_pipeline_evaluation(
        tmp_path,
        ["I cannot decide from this answer.", "done"],
    )

    assert result.stop_reason == "task_done"
    assert result.response == "FINAL"
    assert result.evaluation_attempts == 2
    assert result.degradations == []
    assert "exactly one word" in planner.prompts[-1]
    assert "do not answer the task itself" in planner.prompts[-1].lower()


def test_twice_undecipherable_evaluation_assumes_done_and_declares_it(tmp_path) -> None:
    result, _ = _run_pipeline_evaluation(
        tmp_path,
        ["I cannot decide.", "The answer seems plausible."],
    )

    assert result.stop_reason == "task_done"
    assert result.response == "FINAL"
    assert result.evaluation_attempts == 2
    assert result.degradations == [
        {
            "stage": "evaluate",
            "reason": "undecipherable_decision",
            "action": "assume_done",
        }
    ]


def test_plan_and_evaluate_renegotiation_counters_are_independent(tmp_path) -> None:
    corrected = _derivation(
        "pipeline",
        [{"id": "r1", "text": "do all the work"}],
        [_item("pipeline", "work", ["r1"])],
    )
    result, _ = _run_pipeline_evaluation(
        tmp_path,
        ["No decipherable verdict.", "done"],
        plan_responses=['{"prompt": "reduced work"}', corrected],
    )

    assert result.stop_reason == "task_done"
    assert result.plan_attempts == 2
    assert result.evaluation_attempts == 2
    assert result.degradations == []


def test_valid_evaluation_decision_does_not_renegotiate(tmp_path) -> None:
    result, planner = _run_pipeline_evaluation(tmp_path, ["done"])

    assert result.stop_reason == "task_done"
    assert result.evaluation_attempts == 1
    assert result.degradations == []
    assert len(planner.prompts) == 2  # One PLAN call and one EVALUATE call.
