from __future__ import annotations

from dataclasses import replace

import pytest

from ianest_core.config import EffortConfig, load_config
from ianest_core.errors import CoreError
from ianest_core.runtime import TaskRuntime


def _runtime(fixture: str = "eval/fixtures/orchestration_effort.yaml") -> TaskRuntime:
    return TaskRuntime(load_config(fixture))


def test_effort_resolves_field_by_field_and_keeps_machine_axes() -> None:
    runtime = _runtime()
    partial_settings = replace(
        runtime.settings,
        effort={"low": EffortConfig(max_iterations=1)},
    )
    runtime.settings = partial_settings
    base = runtime
    low = base._runtime_for_effort("low")

    assert low.resolved_effort == "low"
    assert low.settings.max_subtasks == base.settings.max_subtasks == 6
    assert low.settings.max_iterations == 1
    assert low.settings.max_replans == base.settings.max_replans == 1
    assert low.settings.max_time_s == base.settings.max_time_s == 120
    assert low.settings.max_parallel == base.settings.max_parallel == 2
    assert low.settings.coverage is not None
    assert base.settings.coverage is not None
    assert low.settings.coverage.max_chunks == base.settings.coverage.max_chunks == 8
    assert low.settings.coverage.max_retries_per_unit == base.settings.coverage.max_retries_per_unit == 2
    assert low.settings.coverage.units_per_chunk == base.settings.coverage.units_per_chunk == 3
    assert (
        low.settings.coverage.max_no_progress_iterations
        == base.settings.coverage.max_no_progress_iterations
        == 2
    )


def test_undeclared_effort_level_resolves_to_base() -> None:
    base = _runtime()
    medium = base._runtime_for_effort("medium")

    assert "medium" not in base.settings.effort
    assert medium.resolved_effort == "medium"
    assert medium.settings == base.settings


def test_default_effort_is_configurable() -> None:
    runtime = _runtime("eval/fixtures/orchestration_effort_default_low.yaml")
    resolved = runtime._runtime_for_effort(None)

    assert resolved.resolved_effort == "low"
    assert resolved.settings.max_subtasks == 3


def test_invalid_effort_is_typed_config_error() -> None:
    with pytest.raises(CoreError) as exc:
        list(_runtime().stream(prompt="una cosa", effort="xxl"))

    assert exc.value.type == "ConfigError"
    assert exc.value.field == "effort"


def test_effort_does_not_change_token_measurement_for_same_plan() -> None:
    runtime = _runtime()
    plan = [{"prompt": "una cosa"}]
    grants = {
        level: runtime._runtime_for_effort(level)._pipeline_token_grant(plan)
        for level in ("low", "medium", "high")
    }

    assert grants == {"low": 1500, "medium": 1500, "high": 1500}
    assert all(
        runtime._runtime_for_effort(level).settings.token_budget == runtime.settings.token_budget
        for level in ("low", "medium", "high")
    )
