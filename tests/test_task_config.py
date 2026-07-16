from __future__ import annotations

from copy import deepcopy

import pytest

from ianest_core.config import load_config, load_config_data, validate_config_dict
from ianest_core.errors import ConfigValidationError


def test_orchestration_config_loads_frozen_fixture() -> None:
    config = load_config("eval/fixtures/orchestration.yaml")

    assert config.orchestration is not None
    assert config.orchestration.planner.model == "fake_planner"
    assert config.orchestration.combiner.model == "fake_combiner"
    assert config.orchestration.max_replans == 1
    assert config.orchestration.max_parallel == 2


def test_orchestration_config_is_optional() -> None:
    config = load_config("eval/fixtures/config.yaml")

    assert config.orchestration is None


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
