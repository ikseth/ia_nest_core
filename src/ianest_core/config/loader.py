from __future__ import annotations

import os
import re
from pathlib import Path
from typing import Any

import yaml

from ianest_core.config.schema import (
    CoreConfig,
    DomainConfig,
    ModelConfig,
    ProfileConfig,
    TelemetryConfig,
)

ENV_PATTERN = re.compile(r"^\$\{([A-Z0-9_]+)\}$")


def load_config(path: str | Path) -> CoreConfig:
    with Path(path).open("r", encoding="utf-8") as handle:
        raw = yaml.safe_load(handle) or {}

    models = [_load_model(item) for item in raw.get("models", [])]
    domains = [_load_domain(item) for item in raw.get("domains", [])]
    profiles = [_load_profile(item) for item in raw.get("profiles", [])]
    telemetry = _load_telemetry(raw.get("telemetry"))
    identity_defaults = dict(raw.get("identity_defaults", {}))
    return CoreConfig(models, domains, profiles, identity_defaults, telemetry)


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
    extra = dict(raw_params.pop("extra", {}))
    return ProfileConfig(id=profile_id, params=raw_params, extra=extra)


def _load_telemetry(raw: dict[str, Any] | None) -> TelemetryConfig | None:
    if raw is None:
        return None
    return TelemetryConfig(
        csv_path=str(raw.get("csv_path", "")),
        jsonl_path=str(raw.get("jsonl_path", "")),
        rotation=str(raw.get("rotation", "size")),
        strict_mode=bool(raw.get("strict_mode", False)),
    )

