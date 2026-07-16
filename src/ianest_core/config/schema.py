from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any


@dataclass(frozen=True)
class ModelConfig:
    id: str
    provider: str  # backend/runtime que sirve el modelo: fake | ollama | ... (ADR 0029)
    adapter: str
    endpoint: str
    model_name: str
    capabilities: list[str]
    profile: str


@dataclass(frozen=True)
class DomainConfig:
    id: str
    description: str
    preferred_model: str
    fallback_models: list[str]
    profile: str
    routing_rules: dict[str, Any]
    status: str


@dataclass(frozen=True)
class ProfileConfig:
    id: str
    params: dict[str, Any]
    extra: dict[str, Any] = field(default_factory=dict)
    system: str = ""


@dataclass(frozen=True)
class TelemetryConfig:
    csv_path: str
    jsonl_path: str
    rotation: str = "size"
    strict_mode: bool = False


@dataclass(frozen=True)
class OrchestrationTargetConfig:
    model: str | None
    domain: str | None
    profile: str


@dataclass(frozen=True)
class OrchestrationConfig:
    planner: OrchestrationTargetConfig
    combiner: OrchestrationTargetConfig
    max_subtasks: int = 4
    max_iterations: int = 2
    max_replans: int = 1
    max_time_s: float = 30
    max_context_tokens: int = 4096
    max_parallel: int = 2


@dataclass(frozen=True)
class CoreConfig:
    models: list[ModelConfig]
    domains: list[DomainConfig]
    profiles: list[ProfileConfig]
    identity_defaults: dict[str, str]
    telemetry: TelemetryConfig | None
    orchestration: OrchestrationConfig | None = None
