from __future__ import annotations

import os
import re
from pathlib import Path
from typing import Any

import yaml

from ianest_core.config.schema import (
    CoverageConfig,
    CoreConfig,
    DomainConfig,
    ModelConfig,
    OrchestrationConfig,
    OrchestrationTargetConfig,
    ProfileConfig,
    TelemetryConfig,
)
from ianest_core.errors import ConfigError

ENV_PATTERN = re.compile(r"^\$\{([A-Z0-9_]+)\}$")


def load_config(path: str | Path) -> CoreConfig:
    return load_config_from_dict(load_config_data(path))


def load_config_data(path: str | Path) -> dict[str, Any]:
    config_path = Path(path)
    try:
        with config_path.open("r", encoding="utf-8") as handle:
            raw = yaml.safe_load(handle) or {}
    except FileNotFoundError as exc:
        raise ConfigError(f"configuration file not found: {config_path}", "config") from exc
    except yaml.YAMLError as exc:
        raise ConfigError(f"invalid YAML in configuration '{config_path}': {exc}", "config") from exc
    return raw


def load_config_from_dict(raw: dict[str, Any]) -> CoreConfig:
    models = [_load_model(item) for item in raw.get("models", [])]
    domains = [_load_domain(item) for item in raw.get("domains", [])]
    profiles = [_load_profile(item) for item in raw.get("profiles", [])]
    telemetry = _load_telemetry(raw.get("telemetry"))
    identity_defaults = dict(raw.get("identity_defaults", {}))
    orchestration = _load_orchestration(raw.get("orchestration"))
    return CoreConfig(models, domains, profiles, identity_defaults, telemetry, orchestration)


def _resolve_env(value: Any) -> Any:
    if not isinstance(value, str):
        return value
    match = ENV_PATTERN.match(value)
    if not match:
        return value
    return os.environ.get(match.group(1), "")


def _load_model(raw: dict[str, Any]) -> ModelConfig:
    return ModelConfig(
        id=str(raw.get("id", "")),
        provider=str(raw.get("provider", "")),
        adapter=str(raw.get("adapter", "")),
        endpoint=str(_resolve_env(raw.get("endpoint", ""))),
        model_name=str(raw.get("model_name", "")),
        capabilities=list(raw.get("capabilities", [])),
        profile=str(raw.get("profile", "")),
    )


def _load_domain(raw: dict[str, Any]) -> DomainConfig:
    return DomainConfig(
        id=str(raw.get("id", "")),
        description=str(raw.get("description", "")),
        preferred_model=str(raw.get("preferred_model", "")),
        fallback_models=list(raw.get("fallback_models", [])),
        profile=str(raw.get("profile", "")),
        routing_rules=dict(raw.get("routing_rules", {})),
        status=str(raw.get("status", "")),
    )


def _load_profile(raw: dict[str, Any]) -> ProfileConfig:
    raw_params = dict(raw)
    profile_id = str(raw_params.pop("id", ""))
    system = str(raw_params.pop("system", ""))
    extra = dict(raw_params.pop("extra", {}))
    return ProfileConfig(id=profile_id, params=raw_params, extra=extra, system=system)


def _load_telemetry(raw: dict[str, Any] | None) -> TelemetryConfig | None:
    if raw is None:
        return None
    return TelemetryConfig(
        csv_path=str(raw.get("csv_path", "")),
        jsonl_path=str(raw.get("jsonl_path", "")),
        rotation=str(raw.get("rotation", "size")),
        strict_mode=bool(raw.get("strict_mode", False)),
    )


def _load_orchestration(raw: dict[str, Any] | None) -> OrchestrationConfig | None:
    if raw is None:
        return None
    return OrchestrationConfig(
        planner=_load_orchestration_target(raw.get("planner", {})),
        combiner=_load_orchestration_target(raw.get("combiner", {})),
        max_subtasks=int(raw.get("max_subtasks", 4)),
        max_iterations=int(raw.get("max_iterations", 2)),
        max_replans=int(raw.get("max_replans", 1)),
        max_time_s=float(raw.get("max_time_s", 30)),
        max_context_tokens=int(raw.get("max_context_tokens", 4096)),
        max_parallel=int(raw.get("max_parallel", 2)),
        coverage=_load_coverage(raw.get("coverage")),
    )


def _load_coverage(raw: dict[str, Any] | None) -> CoverageConfig | None:
    if raw is None:
        return None
    return CoverageConfig(
        validator=_load_orchestration_target(raw.get("validator", {})),
        units_per_chunk=int(raw.get("units_per_chunk", 3)),
        max_chunks=int(raw.get("max_chunks", 8)),
        max_total_tokens=int(raw.get("max_total_tokens", 16384)),
        max_retries_per_unit=int(raw.get("max_retries_per_unit", 2)),
        max_no_progress_iterations=int(raw.get("max_no_progress_iterations", 2)),
    )


def _load_orchestration_target(raw: dict[str, Any]) -> OrchestrationTargetConfig:
    return OrchestrationTargetConfig(
        model=str(raw["model"]) if raw.get("model") else None,
        domain=str(raw["domain"]) if raw.get("domain") else None,
        profile=str(raw.get("profile", "")),
    )
