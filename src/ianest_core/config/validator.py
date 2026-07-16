from __future__ import annotations

import os
import re
from typing import Any

from ianest_core.errors import ConfigValidationError

ENV_PATTERN = re.compile(r"^\$\{([A-Z0-9_]+)\}$")

MODEL_FIELDS = ["id", "provider", "adapter", "endpoint", "model_name", "capabilities", "profile"]
DOMAIN_FIELDS = [
    "id",
    "description",
    "preferred_model",
    "fallback_models",
    "profile",
    "routing_rules",
    "status",
]
PROFILE_FIELDS = ["id"]
ORCHESTRATION_LIMITS = {
    "max_subtasks": int,
    "max_iterations": int,
    "max_replans": int,
    "max_time_s": (int, float),
    "max_context_tokens": int,
    "max_parallel": int,
}


def validate_config_dict(raw: dict[str, Any]) -> dict[str, Any]:
    _require_section(raw, "models", list)
    _require_section(raw, "domains", list)
    _require_section(raw, "profiles", list)

    models = raw.get("models", [])
    domains = raw.get("domains", [])
    profiles = raw.get("profiles", [])

    for model in models:
        _require_fields(model, MODEL_FIELDS)
        _validate_env_ref(model.get("endpoint"), "endpoint")
        if model.get("adapter") != "openai_compatible":
            raise ConfigValidationError("unsupported adapter", "adapter")
        if not isinstance(model.get("capabilities"), list):
            raise ConfigValidationError("capabilities must be a list", "capabilities")

    for domain in domains:
        _require_fields(domain, DOMAIN_FIELDS)
        if not isinstance(domain.get("fallback_models"), list):
            raise ConfigValidationError("fallback_models must be a list", "fallback_models")
        routing_rules = domain.get("routing_rules")
        if not isinstance(routing_rules, dict):
            raise ConfigValidationError("routing_rules must be a mapping", "routing_rules")
        for key in ("keywords", "tags"):
            if key in routing_rules and not isinstance(routing_rules[key], list):
                raise ConfigValidationError(f"routing_rules.{key} must be a list", "routing_rules")

    for profile in profiles:
        _require_fields(profile, PROFILE_FIELDS)
        if "system" in profile and not isinstance(profile["system"], str):
            raise ConfigValidationError("system must be a string", "system")

    model_ids = _unique_ids(models, "model")
    domain_ids = _unique_ids(domains, "domain")
    profile_ids = _unique_ids(profiles, "profile")

    for model in models:
        if model["profile"] not in profile_ids:
            raise ConfigValidationError("model profile does not exist", "profile")

    for domain in domains:
        if domain["preferred_model"] not in model_ids:
            raise ConfigValidationError("preferred_model does not exist", "preferred_model")
        if domain["profile"] not in profile_ids:
            raise ConfigValidationError("domain profile does not exist", "profile")
        for fallback_model in domain["fallback_models"]:
            if fallback_model not in model_ids:
                raise ConfigValidationError("fallback_model does not exist", "fallback_models")

    orchestration = raw.get("orchestration")
    if orchestration is not None:
        _validate_orchestration(orchestration, model_ids, domain_ids, profile_ids)

    return {"models": model_ids, "domains": domain_ids, "profiles": profile_ids}


def _validate_orchestration(
    raw: Any,
    model_ids: set[str],
    domain_ids: set[str],
    profile_ids: set[str],
) -> None:
    if not isinstance(raw, dict):
        raise ConfigValidationError("orchestration must be a mapping", "orchestration")
    for name in ("planner", "combiner"):
        target = raw.get(name)
        if not isinstance(target, dict):
            raise ConfigValidationError("missing orchestration target", name)
        model = target.get("model")
        domain = target.get("domain")
        if bool(model) == bool(domain):
            raise ConfigValidationError("target requires exactly one of model or domain", name)
        if model and model not in model_ids:
            raise ConfigValidationError("orchestration model does not exist", f"{name}.model")
        if domain and domain not in domain_ids:
            raise ConfigValidationError("orchestration domain does not exist", f"{name}.domain")
        if target.get("profile") not in profile_ids:
            raise ConfigValidationError("orchestration profile does not exist", f"{name}.profile")
    for field, expected_type in ORCHESTRATION_LIMITS.items():
        if field not in raw:
            continue
        value = raw[field]
        if isinstance(value, bool) or not isinstance(value, expected_type) or value <= 0:
            raise ConfigValidationError("orchestration limit must be positive", field)


def _require_section(raw: dict[str, Any], field: str, expected_type: type) -> None:
    if field not in raw:
        raise ConfigValidationError("missing required section", field)
    if not isinstance(raw[field], expected_type):
        raise ConfigValidationError("section has invalid type", field)


def _require_fields(item: dict[str, Any], fields: list[str]) -> None:
    for field in fields:
        if field not in item or item[field] in (None, ""):
            raise ConfigValidationError("missing required field", field)


def _validate_env_ref(value: Any, field: str) -> None:
    if not isinstance(value, str):
        raise ConfigValidationError("endpoint must be a string", field)
    match = ENV_PATTERN.match(value)
    if match and os.environ.get(match.group(1), "") == "":
        raise ConfigValidationError("environment variable is not resolved", field)


def _unique_ids(items: list[dict[str, Any]], label: str) -> set[str]:
    ids: set[str] = set()
    for item in items:
        item_id = str(item.get("id", ""))
        if item_id in ids:
            raise ConfigValidationError(f"duplicate {label} id", "id")
        ids.add(item_id)
    return ids
