from __future__ import annotations

import time
from dataclasses import dataclass
from typing import Any
from uuid import uuid4

from ianest_core.adapters import (
    FakeAdapter,
    ModelAdapter,
    ModelRequest,
    OpenAICompatibleAdapter,
    run_blocking,
)
from ianest_core.config.schema import CoreConfig, ModelConfig
from ianest_core.errors import CoreError
from ianest_core.identity import Identity
from ianest_core.memory import MemoryPort, NullMemoryAdapter
from ianest_core.registry import ModelRegistry
from ianest_core.telemetry import TelemetryWriter


@dataclass(frozen=True)
class PromptRunResult:
    response: str
    model: str
    domain: str
    params: dict[str, Any]
    trace: dict[str, Any]

    def to_dict(self) -> dict[str, Any]:
        return {
            "response": self.response,
            "model": self.model,
            "domain": self.domain,
            "params": self.params,
            "trace": self.trace,
        }


class PromptRuntime:
    def __init__(
        self,
        config: CoreConfig,
        telemetry: TelemetryWriter | None = None,
        memory: MemoryPort | None = None,
    ) -> None:
        self.config = config
        self.registry = ModelRegistry(config)
        self.telemetry = telemetry or TelemetryWriter(config.telemetry)
        self.memory = memory or NullMemoryAdapter()

    def run(
        self,
        *,
        prompt: str,
        model_id: str | None = None,
        domain_id: str | None = None,
        identity_override: dict[str, str] | None = None,
        request_id: str | None = None,
    ) -> PromptRunResult:
        started = time.monotonic()
        request_id = request_id or str(uuid4())
        resolved = self.registry.resolve_prompt_target(model_id, domain_id)
        domain = resolved.domain.id if resolved.domain is not None else ""
        identity_data = dict(identity_override or {})
        if domain and not identity_data.get("domain_tag"):
            identity_data["domain_tag"] = domain
        identity = Identity.from_defaults(self.config.identity_defaults, identity_data)
        params = dict(resolved.profile.params)
        extra = dict(resolved.profile.extra)
        adapter = self._adapter_for(resolved.model)
        req = ModelRequest(messages=[{"role": "user", "content": prompt}], params=params, extra=extra)

        self.memory.read_context(identity)
        self.telemetry.record(
            request_id=request_id,
            event="request_start",
            capability="prompt.run",
            identity=identity,
            payload={"prompt": prompt},
            domain=domain,
            model=resolved.model.id,
        )
        self.telemetry.record(
            request_id=request_id,
            event="model_call",
            capability="prompt.run",
            identity=identity,
            payload={"model_name": resolved.model.model_name, "adapter": resolved.model.adapter},
            domain=domain,
            model=resolved.model.id,
        )

        try:
            response = run_blocking(adapter, req)
        except CoreError as exc:
            latency_ms = _latency_ms(started)
            self.telemetry.record(
                request_id=request_id,
                event="error",
                capability="prompt.run",
                identity=identity,
                payload=exc.to_dict(),
                domain=domain,
                model=resolved.model.id,
                latency_ms=latency_ms,
                status="error",
                error_type=exc.type,
            )
            raise

        latency_ms = _latency_ms(started)
        trace = {
            "request_id": request_id,
            "capability": "prompt.run",
            "user_id": identity.user_id,
            "service": identity.service,
            "session_id": identity.session_id,
            "domain_tag": identity.domain_tag,
            "namespace": identity.namespace,
            "domain": domain,
            "model": resolved.model.id,
            "latency_ms": latency_ms,
            "tokens_in": response.tokens_in,
            "tokens_out": response.tokens_out,
            "status": "ok",
        }
        self.telemetry.record(
            request_id=request_id,
            event="done",
            capability="prompt.run",
            identity=identity,
            payload={"response": response.text},
            domain=domain,
            model=resolved.model.id,
            latency_ms=latency_ms,
            tokens_in=response.tokens_in,
            tokens_out=response.tokens_out,
            status="ok",
        )
        return PromptRunResult(
            response=response.text,
            model=resolved.model.id,
            domain=domain,
            params=params,
            trace=trace,
        )

    def _adapter_for(self, model: ModelConfig) -> ModelAdapter:
        if model.provider == "fake" or model.endpoint.startswith("fake://"):
            return FakeAdapter(model=model.id)
        return OpenAICompatibleAdapter(endpoint=model.endpoint, model_name=model.model_name)


def _latency_ms(started: float) -> int:
    return int((time.monotonic() - started) * 1000)

