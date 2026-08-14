from __future__ import annotations

from copy import deepcopy

import pytest

from ianest_core.config import load_config, load_config_data, validate_config_dict
from ianest_core.errors import ConfigValidationError


def test_domain_config_does_not_expose_routing_rules() -> None:
    raw = load_config_data("eval/fixtures/router.yaml")

    validate_config_dict(raw)
    config = load_config("eval/fixtures/router.yaml")

    assert all(not hasattr(domain, "routing_rules") for domain in config.domains)


def test_config_accepts_valid_router_and_default_domain() -> None:
    raw = load_config_data("eval/fixtures/router.yaml")

    validate_config_dict(raw)
    config = load_config("eval/fixtures/router.yaml")

    assert config.router is not None
    assert config.router.model == "fake_router"
    assert config.router.domain is None
    assert config.router.profile == "default"
    assert config.default_domain == "general"


@pytest.mark.parametrize(
    "router",
    [
        {"model": "fake_router", "domain": "general", "profile": "default"},
        {"profile": "default"},
    ],
)
def test_config_rejects_router_without_exactly_one_target(router: dict[str, str]) -> None:
    raw = deepcopy(load_config_data("eval/fixtures/router.yaml"))
    raw["router"] = router

    with pytest.raises(ConfigValidationError) as exc:
        validate_config_dict(raw)

    assert exc.value.field == "router"


@pytest.mark.parametrize(
    ("router", "field"),
    [
        ({"model": "missing", "profile": "default"}, "router.model"),
        ({"domain": "missing", "profile": "default"}, "router.domain"),
    ],
)
def test_config_rejects_unknown_router_target(router: dict[str, str], field: str) -> None:
    raw = deepcopy(load_config_data("eval/fixtures/router.yaml"))
    raw["router"] = router

    with pytest.raises(ConfigValidationError) as exc:
        validate_config_dict(raw)

    assert exc.value.field == field


def test_config_rejects_unknown_default_domain() -> None:
    raw = deepcopy(load_config_data("eval/fixtures/router.yaml"))
    raw["default_domain"] = "missing"

    with pytest.raises(ConfigValidationError) as exc:
        validate_config_dict(raw)

    assert exc.value.field == "default_domain"


def test_config_rejects_routing_rules_regardless_of_shape() -> None:
    raw = deepcopy(load_config_data("eval/fixtures/config.yaml"))
    raw["domains"][0]["routing_rules"] = {"keywords": "error"}

    with pytest.raises(ConfigValidationError) as exc:
        validate_config_dict(raw)

    assert exc.value.field == "routing_rules"


def test_config_rejects_empty_routing_rules() -> None:
    raw = deepcopy(load_config_data("eval/fixtures/config.yaml"))
    raw["domains"][0]["routing_rules"] = {}

    with pytest.raises(ConfigValidationError) as exc:
        validate_config_dict(raw)

    assert exc.value.field == "routing_rules"


def test_routing_rules_rejection_names_router_migration() -> None:
    raw = deepcopy(load_config_data("eval/fixtures/config.yaml"))
    raw["domains"][0]["routing_rules"] = {"tags": ["legacy"]}

    with pytest.raises(ConfigValidationError) as exc:
        validate_config_dict(raw)

    assert "router" in exc.value.message
