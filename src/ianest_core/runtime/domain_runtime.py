from __future__ import annotations

import time
from dataclasses import dataclass
from typing import Any
from uuid import uuid4

from ianest_core.config.schema import CoreConfig
from ianest_core.domain_router import DomainRouter
from ianest_core.identity import Identity
from ianest_core.registry import AvailabilityProvider, ModelRegistry
from ianest_core.telemetry import TelemetryWriter


@dataclass(frozen=True)
class DomainRouteResult:
    domain: str
    model: str
    substituted: bool
    preferred_model: str
    confidence: float
    reason: str
    alternatives: list[dict[str, str | float]]
    trace: dict[str, Any]

    def to_dict(self) -> dict[str, Any]:
        return {
            "domain": self.domain,
            "model": self.model,
            "substituted": self.substituted,
            "preferred_model": self.preferred_model,
            "confidence": self.confidence,
            "reason": self.reason,
            "alternatives": self.alternatives,
            "trace": self.trace,
        }


class DomainRuntime:
    def __init__(
        self,
        config: CoreConfig,
        telemetry: TelemetryWriter | None = None,
        availability: AvailabilityProvider | None = None,
    ) -> None:
        self.config = config
        self.registry = ModelRegistry(config, availability=availability)
        self.router = DomainRouter(self.registry)
        self.telemetry = telemetry or TelemetryWriter(config.telemetry)

    def route(
        self,
        *,
        prompt: str,
        identity_override: dict[str, str] | None = None,
        request_id: str | None = None,
        tags: list[str] | None = None,
    ) -> DomainRouteResult:
        started = time.monotonic()
        request_id = request_id or str(uuid4())
        route = self.router.route(prompt, tags=tags)
        identity_data = dict(identity_override or {})
        if not identity_data.get("domain_tag"):
            identity_data["domain_tag"] = route.domain
        identity = Identity.from_defaults(self.config.identity_defaults, identity_data)
        latency_ms = int((time.monotonic() - started) * 1000)
        trace = {
            "request_id": request_id,
            "capability": "domain.route",
            "user_id": identity.user_id,
            "service": identity.service,
            "session_id": identity.session_id,
            "domain_tag": identity.domain_tag,
            "namespace": identity.namespace,
            "domain": route.domain,
            "model": route.model,
            "latency_ms": latency_ms,
            "status": "ok",
        }
        self.telemetry.record(
            request_id=request_id,
            event="route",
            capability="domain.route",
            identity=identity,
            payload=route.to_dict(),
            domain=route.domain,
            model=route.model,
            latency_ms=latency_ms,
            status="ok",
        )
        return DomainRouteResult(
            domain=route.domain,
            model=route.model,
            substituted=route.substituted,
            preferred_model=route.preferred_model,
            confidence=route.confidence,
            reason=route.reason,
            alternatives=route.alternatives,
            trace=trace,
        )
