from __future__ import annotations

from copy import deepcopy

import pytest

from ianest_core.config import load_config, load_config_data, load_config_from_dict, validate_config_dict
from ianest_core.config.loader import _load_orchestration
from ianest_core.config.schema import OrchestrationConfig, TokenBudgetConfig
from ianest_core.errors import ConfigValidationError


def test_orchestration_config_loads_frozen_fixture() -> None:
    config = load_config("eval/fixtures/orchestration.yaml")

    assert config.orchestration is not None
    assert config.orchestration.planner.model == "fake_planner"
    assert config.orchestration.combiner.model == "fake_combiner"
    assert config.orchestration.max_replans == 1
    assert config.orchestration.max_parallel == 2


def test_orchestration_loader_defaults_match_the_schema() -> None:
    minimal = {
        "planner": {"model": "fake_planner"},
        "combiner": {"model": "fake_combiner"},
    }
    loaded = _load_orchestration(minimal)
    declared = OrchestrationConfig(planner=loaded.planner, combiner=loaded.combiner)

    for field in ("max_subtasks", "max_iterations", "max_replans", "max_time_s",
                  "max_parallel", "token_budget", "default_effort", "effort"):
        assert getattr(loaded, field) == getattr(declared, field), field
    assert loaded.token_budget == TokenBudgetConfig(base=2000, per_subtask=3000)
    assert loaded.max_subtasks == 6
    assert loaded.max_time_s == 120
    assert loaded.default_effort == "medium"


def test_orchestration_config_is_optional() -> None:
    config = load_config("eval/fixtures/config.yaml")

    assert config.orchestration is None


def test_orchestration_coverage_config_loads_frozen_fixture() -> None:
    validate_config_dict(load_config_data("eval/fixtures/orchestration_coverage.yaml"))
    config = load_config("eval/fixtures/orchestration_coverage.yaml")

    assert config.orchestration is not None
    assert config.orchestration.coverage is not None
    assert config.orchestration.coverage.validator.model == "fake_validator"
    assert config.orchestration.coverage.units_per_chunk == 3
    assert config.orchestration.coverage.max_chunks == 8
    assert config.orchestration.coverage.max_retries_per_unit == 2
    assert config.orchestration.coverage.max_no_progress_iterations == 2


def test_orchestration_coverage_config_is_optional() -> None:
    validate_config_dict(load_config_data("eval/fixtures/orchestration.yaml"))
    config = load_config("eval/fixtures/orchestration.yaml")

    assert config.orchestration is not None
    assert config.orchestration.coverage is None


def test_retired_task_token_limits_validate_and_are_ignored() -> None:
    raw = deepcopy(load_config_data("eval/fixtures/orchestration_coverage.yaml"))
    raw["orchestration"]["max_context_tokens"] = "ignored even with the old wrong type"
    raw["orchestration"]["coverage"]["max_total_tokens"] = False

    validate_config_dict(raw)
    config = load_config_from_dict(raw)

    assert config.orchestration is not None
    assert not hasattr(config.orchestration, "max_context_tokens")
    assert config.orchestration.coverage is not None
    assert not hasattr(config.orchestration.coverage, "max_total_tokens")


@pytest.mark.parametrize(
    ("mutation", "field"),
    [
        ({"planner": {"model": "missing", "profile": "default"}}, "planner.model"),
        ({"planner": {"domain": "missing", "profile": "default"}}, "planner.domain"),
        ({"planner": {"model": "fake_planner", "domain": "general", "profile": "default"}}, "planner"),
        ({"combiner": {"model": "fake_combiner", "profile": "missing"}}, "combiner.profile"),
        ({"max_parallel": 0}, "max_parallel"),
    ],
)
def test_orchestration_validator_rejects_invalid_references_and_limits(mutation, field) -> None:
    raw = deepcopy(load_config_data("eval/fixtures/orchestration.yaml"))
    raw["orchestration"].update(mutation)

    with pytest.raises(ConfigValidationError) as exc:
        validate_config_dict(raw)

    assert exc.value.field == field


@pytest.mark.parametrize(
    ("mutation", "field"),
    [
        ({"validator": {"model": "missing", "profile": "default"}}, "orchestration.coverage.validator.model"),
        ({"max_chunks": 0}, "orchestration.coverage.max_chunks"),
    ],
)
def test_orchestration_coverage_validator_rejects_invalid_references_and_limits(mutation, field) -> None:
    raw = deepcopy(load_config_data("eval/fixtures/orchestration_coverage.yaml"))
    raw["orchestration"]["coverage"].update(mutation)

    with pytest.raises(ConfigValidationError) as exc:
        validate_config_dict(raw)

    assert exc.value.field == field


@pytest.mark.parametrize(
    ("mutation", "field"),
    [
        ({"default_effort": "xxl"}, "orchestration.default_effort"),
        ({"effort": []}, "orchestration.effort"),
        ({"effort": {"xxl": {"max_subtasks": 2}}}, "orchestration.effort.xxl"),
        ({"effort": {"low": {"max_replans": -1}}}, "orchestration.effort.low.max_replans"),
        (
            {"effort": {"high": {"coverage": {"max_chunks": 0}}}},
            "orchestration.effort.high.coverage.max_chunks",
        ),
    ],
)
def test_orchestration_effort_validator_rejects_invalid_values(mutation, field) -> None:
    raw = deepcopy(load_config_data("eval/fixtures/orchestration_effort.yaml"))
    raw["orchestration"].update(mutation)

    with pytest.raises(ConfigValidationError) as exc:
        validate_config_dict(raw)

    assert exc.value.field == field
