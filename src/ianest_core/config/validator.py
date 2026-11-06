from __future__ import annotations

import os
import re
from typing import Any

from ianest_core.errors import ConfigValidationError
from ianest_core.identity import INTERLOCUTOR_PROFILES

ENV_PATTERN = re.compile(r"^\$\{([A-Z0-9_]+)\}$")
ENV_NAME_PATTERN = re.compile(r"^[A-Z_][A-Z0-9_]*$")

MODEL_FIELDS = ["id", "provider", "adapter", "endpoint", "model_name", "capabilities", "profile"]
DOMAIN_FIELDS = [
    "id",
    "description",
    "preferred_model",
    "fallback_models",
    "profile",
    "status",
]
PROFILE_FIELDS = ["id"]
ORCHESTRATION_LIMITS = {
    "max_subtasks": int,
    "max_iterations": int,
    "max_replans": int,
    "max_time_s": (int, float),
    "max_parallel": int,
}
COVERAGE_LIMITS = {
    "units_per_chunk": int,
    "max_chunks": int,
    "max_retries_per_unit": int,
    "max_no_progress_iterations": int,
}
EFFORT_LEVELS = {"low", "medium", "high"}
EFFORT_LIMITS = {
    "max_subtasks": int,
    "max_iterations": int,
    "max_replans": int,
    "max_time_s": (int, float),
}
EFFORT_COVERAGE_LIMITS = {
    "max_chunks": int,
    "max_retries_per_unit": int,
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
        if "routing_rules" in domain:
            raise ConfigValidationError(
                "routing_rules was retired: routing is semantic. Declare 'router' and "
                "describe each domain in its 'description'.",
                "routing_rules",
            )
        _require_fields(domain, DOMAIN_FIELDS)
        if not isinstance(domain.get("fallback_models"), list):
            raise ConfigValidationError("fallback_models must be a list", "fallback_models")

    for profile in profiles:
        _require_fields(profile, PROFILE_FIELDS)
        if "system" in profile and not isinstance(profile["system"], str):
            raise ConfigValidationError("system must be a string", "system")

    model_ids = _unique_ids(models, "model")
    domain_ids = _unique_ids(domains, "domain")
    profile_ids = _unique_ids(profiles, "profile")
    provider_ids = _validate_tool_providers(raw.get("tool_providers"))

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
        tools = domain.get("tools")
        if tools is not None:
            _validate_domain_tools(tools, provider_ids)

    orchestration = raw.get("orchestration")
    if orchestration is not None:
        _validate_orchestration(orchestration, model_ids, domain_ids, profile_ids)

    router = raw.get("router")
    if router is not None:
        _validate_orchestration_target(router, "router", model_ids, domain_ids, profile_ids)

    default_domain = raw.get("default_domain")
    if default_domain is not None and default_domain not in domain_ids:
        raise ConfigValidationError("default_domain does not exist", "default_domain")

    return {"models": model_ids, "domains": domain_ids, "profiles": profile_ids}


def _validate_tool_providers(raw: Any) -> set[str]:
    if raw is None:
        return set()
    if not isinstance(raw, dict):
        raise ConfigValidationError("tool_providers must be a mapping", "tool_providers")
    provider_ids: set[str] = set()
    for provider_id, provider in raw.items():
        field = f"tool_providers.{provider_id}"
        if not isinstance(provider_id, str) or not provider_id:
            raise ConfigValidationError("tool provider id must not be empty", "tool_providers")
        if not isinstance(provider, dict):
            raise ConfigValidationError("tool provider must be a mapping", field)
        unknown = set(provider) - {"transport", "url", "auth_env", "timeout_s"}
        if unknown:
            raise ConfigValidationError(
                "unknown tool provider field",
                f"{field}.{sorted(unknown)[0]}",
            )
        if provider.get("transport") != "streamable_http":
            raise ConfigValidationError(
                "tool provider transport must be streamable_http",
                f"{field}.transport",
            )
        if not isinstance(provider.get("url"), str) or not provider["url"]:
            raise ConfigValidationError("tool provider url must not be empty", f"{field}.url")
        auth_env = provider.get("auth_env")
        if auth_env is not None and (
            not isinstance(auth_env, str) or not ENV_NAME_PATTERN.fullmatch(auth_env)
        ):
            raise ConfigValidationError(
                "tool provider auth_env must be an environment variable name",
                f"{field}.auth_env",
            )
        timeout_s = provider.get("timeout_s", 10)
        if isinstance(timeout_s, bool) or not isinstance(timeout_s, (int, float)) or timeout_s <= 0:
            raise ConfigValidationError(
                "tool provider timeout_s must be positive",
                f"{field}.timeout_s",
            )
        provider_ids.add(provider_id)
    return provider_ids


def _validate_domain_tools(raw: Any, provider_ids: set[str]) -> None:
    if not isinstance(raw, dict):
        raise ConfigValidationError("domain tools must be a mapping", "tools")
    unknown = set(raw) - {"provider", "max_rounds", "allow", "deny"}
    if unknown:
        raise ConfigValidationError("unknown domain tools field", f"tools.{sorted(unknown)[0]}")
    provider = raw.get("provider")
    if not isinstance(provider, str) or not provider:
        raise ConfigValidationError("domain tools provider is required", "tools.provider")
    if provider not in provider_ids:
        raise ConfigValidationError("tool provider does not exist", "tools.provider")
    max_rounds = raw.get("max_rounds", 4)
    if isinstance(max_rounds, bool) or not isinstance(max_rounds, int) or max_rounds < 1:
        raise ConfigValidationError("tools max_rounds must be at least 1", "tools.max_rounds")
    allow = raw.get("allow")
    if not isinstance(allow, dict):
        raise ConfigValidationError("tools allow must be a mapping", "tools.allow")
    for profile, names in allow.items():
        if profile not in INTERLOCUTOR_PROFILES:
            raise ConfigValidationError(
                "tools allow profile must be adult or child",
                f"tools.allow.{profile}",
            )
        _validate_tool_name_list(names, f"tools.allow.{profile}")
    deny = raw.get("deny")
    if deny is not None:
        _validate_tool_name_list(deny, "tools.deny")


def _validate_tool_name_list(raw: Any, field: str) -> None:
    if not isinstance(raw, list) or any(not isinstance(name, str) or not name for name in raw):
        raise ConfigValidationError("tool names must be a list of non-empty strings", field)


def _validate_orchestration(
    raw: Any,
    model_ids: set[str],
    domain_ids: set[str],
    profile_ids: set[str],
) -> None:
    if not isinstance(raw, dict):
        raise ConfigValidationError("orchestration must be a mapping", "orchestration")
    for name in ("planner", "combiner"):
        _validate_orchestration_target(raw.get(name), name, model_ids, domain_ids, profile_ids)
    for field, expected_type in ORCHESTRATION_LIMITS.items():
        if field not in raw:
            continue
        value = raw[field]
        if isinstance(value, bool) or not isinstance(value, expected_type) or value <= 0:
            raise ConfigValidationError("orchestration limit must be positive", field)
    token_budget = raw.get("token_budget")
    if token_budget is not None:
        _validate_token_budget(token_budget)
    coverage = raw.get("coverage")
    if coverage is not None:
        _validate_coverage(coverage, model_ids, domain_ids, profile_ids)
    default_effort = raw.get("default_effort")
    if default_effort is not None and default_effort not in EFFORT_LEVELS:
        raise ConfigValidationError(
            "default_effort must be low, medium or high",
            "orchestration.default_effort",
        )
    effort = raw.get("effort")
    if effort is not None:
        _validate_effort(effort)


def _validate_token_budget(raw: Any) -> None:
    if not isinstance(raw, dict):
        raise ConfigValidationError("token_budget must be a mapping", "orchestration.token_budget")
    for name in ("base", "per_subtask"):
        if name not in raw:
            continue
        value = raw[name]
        if isinstance(value, bool) or not isinstance(value, int) or value <= 0:
            raise ConfigValidationError(
                "token budget values must be positive integers",
                f"orchestration.token_budget.{name}",
            )


def _validate_coverage(
    raw: Any,
    model_ids: set[str],
    domain_ids: set[str],
    profile_ids: set[str],
) -> None:
    if not isinstance(raw, dict):
        raise ConfigValidationError("coverage must be a mapping", "orchestration.coverage")
    target = raw.get("validator")
    field = "orchestration.coverage.validator"
    _validate_orchestration_target(target, field, model_ids, domain_ids, profile_ids)
    _validate_coverage_limits(raw)


def _validate_orchestration_target(
    target: Any,
    field: str,
    model_ids: set[str],
    domain_ids: set[str],
    profile_ids: set[str],
) -> None:
    if not isinstance(target, dict):
        raise ConfigValidationError("missing orchestration target", field)
    model = target.get("model")
    domain = target.get("domain")
    if bool(model) == bool(domain):
        raise ConfigValidationError("target requires exactly one of model or domain", field)
    if model and model not in model_ids:
        raise ConfigValidationError("orchestration model does not exist", f"{field}.model")
    if domain and domain not in domain_ids:
        raise ConfigValidationError("orchestration domain does not exist", f"{field}.domain")
    if target.get("profile") not in profile_ids:
        raise ConfigValidationError("orchestration profile does not exist", f"{field}.profile")


def _validate_coverage_limits(raw: dict[str, Any]) -> None:
    for name, expected_type in COVERAGE_LIMITS.items():
        if name not in raw:
            continue
        value = raw[name]
        if isinstance(value, bool) or not isinstance(value, expected_type) or value <= 0:
            raise ConfigValidationError("coverage limit must be positive", f"orchestration.coverage.{name}")


def _validate_effort(raw: Any) -> None:
    if not isinstance(raw, dict):
        raise ConfigValidationError("effort must be a mapping", "orchestration.effort")
    for level, values in raw.items():
        if level not in EFFORT_LEVELS:
            raise ConfigValidationError("unknown effort level", f"orchestration.effort.{level}")
        if not isinstance(values, dict):
            raise ConfigValidationError("effort level must be a mapping", f"orchestration.effort.{level}")
        for name, expected_type in EFFORT_LIMITS.items():
            if name not in values:
                continue
            value = values[name]
            minimum = 0 if name == "max_replans" else 1
            if isinstance(value, bool) or not isinstance(value, expected_type) or value < minimum:
                raise ConfigValidationError(
                    "effort limit is invalid",
                    f"orchestration.effort.{level}.{name}",
                )
        coverage = values.get("coverage")
        if coverage is None:
            continue
        if not isinstance(coverage, dict):
            raise ConfigValidationError(
                "effort coverage must be a mapping",
                f"orchestration.effort.{level}.coverage",
            )
        for name, expected_type in EFFORT_COVERAGE_LIMITS.items():
            if name not in coverage:
                continue
            value = coverage[name]
            if isinstance(value, bool) or not isinstance(value, expected_type) or value <= 0:
                raise ConfigValidationError(
                    "effort coverage limit must be positive",
                    f"orchestration.effort.{level}.coverage.{name}",
                )


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
