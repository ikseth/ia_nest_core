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
class TokenBudgetConfig:
    base: int = 2000
    per_subtask: int = 3000


@dataclass(frozen=True)
class RouterConfig:
    model: str | None
    domain: str | None
    profile: str


@dataclass(frozen=True)
class CoverageConfig:
    validator: OrchestrationTargetConfig
    units_per_chunk: int = 3
    max_chunks: int = 8
    max_retries_per_unit: int = 2
    max_no_progress_iterations: int = 2


@dataclass(frozen=True)
class EffortCoverageConfig:
    max_chunks: int | None = None
    max_retries_per_unit: int | None = None


@dataclass(frozen=True)
class EffortConfig:
    max_subtasks: int | None = None
    max_iterations: int | None = None
    max_replans: int | None = None
    max_time_s: float | None = None
    coverage: EffortCoverageConfig | None = None


@dataclass(frozen=True)
class OrchestrationConfig:
    planner: OrchestrationTargetConfig
    combiner: OrchestrationTargetConfig
    max_subtasks: int = 6
    max_iterations: int = 2
    max_replans: int = 1
    max_time_s: float = 120
    max_parallel: int = 2
    token_budget: TokenBudgetConfig = field(default_factory=TokenBudgetConfig)
    coverage: CoverageConfig | None = None
    default_effort: str = "medium"
    effort: dict[str, EffortConfig] = field(default_factory=dict)


@dataclass(frozen=True)
class CoreConfig:
    models: list[ModelConfig]
    domains: list[DomainConfig]
    profiles: list[ProfileConfig]
    identity_defaults: dict[str, str]
    telemetry: TelemetryConfig | None
    orchestration: OrchestrationConfig | None = None
    router: RouterConfig | None = None
    default_domain: str | None = None
