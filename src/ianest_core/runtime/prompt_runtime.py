from __future__ import annotations

import time
from dataclasses import dataclass
from typing import Any, Callable
from uuid import uuid4

from ianest_core.adapters import (
    FakeAdapter,
    ModelAdapter,
    ModelRequest,
    OpenAICompatibleAdapter,
    run_blocking,
)
from ianest_core.config.schema import CoreConfig, ModelConfig
from ianest_core.domain_router import DomainRouter
from ianest_core.errors import CoreError
from ianest_core.identity import Identity
from ianest_core.registry import AvailabilityProvider, ModelRegistry, ResolvedModel
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


@dataclass(frozen=True)
class PreparedPrompt:
    started: float
    request_id: str
    resolved: ResolvedModel
    domain: str
    identity: Identity
    params: dict[str, Any]
    adapter: ModelAdapter
    req: ModelRequest
    capability: str
    trace_payload: dict[str, Any]


class PromptRuntime:
    def __init__(
        self,
        config: CoreConfig,
        telemetry: TelemetryWriter | None = None,
        availability: AvailabilityProvider | None = None,
        adapter_factory: Callable[[ModelConfig], ModelAdapter | None] | None = None,
    ) -> None:
        self.config = config
        self.registry = ModelRegistry(config, availability=availability)
        self.router = DomainRouter(self.registry)
        self.telemetry = telemetry or TelemetryWriter(config.telemetry)
        self.adapter_factory = adapter_factory

    def run(
        self,
        *,
        prompt: str,
        model_id: str | None = None,
        domain_id: str | None = None,
        identity_override: dict[str, str] | None = None,
        request_id: str | None = None,
        trace_payload: dict[str, Any] | None = None,
        profile_id: str | None = None,
    ) -> PromptRunResult:
        prepared = self._prepare(
            prompt=prompt,
            model_id=model_id,
            domain_id=domain_id,
            identity_override=identity_override,
            request_id=request_id,
            capability="prompt.run",
            trace_payload=trace_payload,
            profile_id=profile_id,
        )

        try:
            response = run_blocking(prepared.adapter, prepared.req)
        except CoreError as exc:
            self._record_error(prepared, exc.to_dict(), exc.type)
            raise

        latency_ms = _latency_ms(prepared.started)
        trace = {
            "request_id": prepared.request_id,
            "capability": "prompt.run",
            "user_id": prepared.identity.user_id,
            "service": prepared.identity.service,
            "session_id": prepared.identity.session_id,
            "domain_tag": prepared.identity.domain_tag,
            "namespace": prepared.identity.namespace,
            "domain": prepared.domain,
            "model": prepared.resolved.model.id,
            "latency_ms": latency_ms,
            "tokens_in": response.tokens_in,
            "tokens_out": response.tokens_out,
            "finish_reason": response.finish_reason,
            "status": "ok",
            "substituted": prepared.resolved.substituted,
            "preferred_model": prepared.resolved.preferred_model,
        }
        self.telemetry.record(
            request_id=prepared.request_id,
            event="done",
            capability="prompt.run",
            identity=prepared.identity,
            payload={"response": response.text, "finish_reason": response.finish_reason, **prepared.trace_payload},
            domain=prepared.domain,
            model=prepared.resolved.model.id,
            latency_ms=latency_ms,
            tokens_in=response.tokens_in,
            tokens_out=response.tokens_out,
            status="ok",
        )
        return PromptRunResult(
            response=response.text,
            model=prepared.resolved.model.id,
            domain=prepared.domain,
            params=prepared.params,
            trace=trace,
        )

    def stream(
        self,
        *,
        prompt: str,
        model_id: str | None = None,
        domain_id: str | None = None,
        identity_override: dict[str, str] | None = None,
        request_id: str | None = None,
    ):
        prepared = self._prepare(
            prompt=prompt,
            model_id=model_id,
            domain_id=domain_id,
            identity_override=identity_override,
            request_id=request_id,
            capability="prompt.run",
        )

        text_parts: list[str] = []
        tokens_in = 0
        tokens_out = 0
        finish_reason: Any = None
        completed = False
        for event in prepared.adapter.stream(prepared.req):
            if event.type == "token":
                text_parts.append(str(event.data.get("text", "")))
            elif event.type == "done":
                tokens_in = int(event.data.get("tokens_in", 0) or 0)
                tokens_out = int(event.data.get("tokens_out", 0) or 0)
                finish_reason = event.data.get("finish_reason")
                completed = True
            elif event.type == "error":
                error_type = str(event.data.get("type", "AdapterError"))
                self._record_error(prepared, event.data, error_type)
                yield event
                return

            yield event
            if completed:
                break

        if not completed:
            return

        latency_ms = _latency_ms(prepared.started)
        self.telemetry.record(
            request_id=prepared.request_id,
            event="done",
            capability="prompt.run",
            identity=prepared.identity,
            payload={"response": "".join(text_parts), "finish_reason": finish_reason},
            domain=prepared.domain,
            model=prepared.resolved.model.id,
            latency_ms=latency_ms,
            tokens_in=tokens_in,
            tokens_out=tokens_out,
            status="ok",
        )

    def _prepare(
        self,
        *,
        prompt: str,
        model_id: str | None,
        domain_id: str | None,
        identity_override: dict[str, str] | None,
        request_id: str | None,
        capability: str = "prompt.run",
        trace_payload: dict[str, Any] | None = None,
        profile_id: str | None = None,
    ) -> PreparedPrompt:
        started = time.monotonic()
        request_id = request_id or str(uuid4())
        route = None
        if model_id is None and domain_id is None:
            route = self.router.route(prompt)
            resolved = route.resolved
        else:
            resolved = self.registry.resolve_prompt_target(model_id, domain_id)
        domain = resolved.domain.id if resolved.domain is not None else ""
        identity_data = dict(identity_override or {})
        if domain and not identity_data.get("domain_tag"):
            identity_data["domain_tag"] = domain
        identity = Identity.from_defaults(self.config.identity_defaults, identity_data)
        if profile_id is not None:
            resolved = ResolvedModel(
                model=resolved.model,
                domain=resolved.domain,
                profile=self.registry.profile(profile_id),
                substituted=resolved.substituted,
                preferred_model=resolved.preferred_model,
            )
        params = dict(resolved.profile.params)
        extra = dict(resolved.profile.extra)
        adapter = self._adapter_for(resolved.model)
        messages = _messages_with_system(prompt, resolved.profile.system)
        req = ModelRequest(messages=messages, params=params, extra=extra)

        self.telemetry.record(
            request_id=request_id,
            event="request_start",
            capability=capability,
            identity=identity,
            payload={"prompt": prompt, **(trace_payload or {})},
            domain=domain,
            model=resolved.model.id,
        )
        if route is not None or resolved.substituted:
            payload = route.to_dict() if route is not None else {}
            if resolved.substituted:
                payload = {
                    **payload,
                    "substituted": True,
                    "preferred_model": resolved.preferred_model,
                    "model": resolved.model.id,
                }
            self.telemetry.record(
                request_id=request_id,
                event="route",
                capability=capability,
                identity=identity,
                payload=payload,
                domain=domain,
                model=resolved.model.id,
            )
        self.telemetry.record(
            request_id=request_id,
            event="model_call",
            capability=capability,
            identity=identity,
            payload={"model_name": resolved.model.model_name, "adapter": resolved.model.adapter},
            domain=domain,
            model=resolved.model.id,
        )
        return PreparedPrompt(
            started=started,
            request_id=request_id,
            resolved=resolved,
            domain=domain,
            identity=identity,
            params=params,
            adapter=adapter,
            req=req,
            capability=capability,
            trace_payload=dict(trace_payload or {}),
        )

    def _record_error(self, prepared: PreparedPrompt, payload: dict[str, Any], error_type: str) -> None:
        self.telemetry.record(
            request_id=prepared.request_id,
            event="error",
            capability=prepared.capability,
            identity=prepared.identity,
            payload=payload,
            domain=prepared.domain,
            model=prepared.resolved.model.id,
            latency_ms=_latency_ms(prepared.started),
            status="error",
            error_type=error_type,
        )

    def _adapter_for(self, model: ModelConfig) -> ModelAdapter:
        if self.adapter_factory is not None:
            adapter = self.adapter_factory(model)
            if adapter is not None:
                return adapter
        if model.provider == "fake" or model.endpoint.startswith("fake://"):
            return FakeAdapter(model=model.id)
        return OpenAICompatibleAdapter(endpoint=model.endpoint, model_name=model.model_name)


def _latency_ms(started: float) -> int:
    return int((time.monotonic() - started) * 1000)


def _messages_with_system(prompt: str, system: str) -> list[dict[str, str]]:
    messages: list[dict[str, str]] = []
    if system:
        messages.append({"role": "system", "content": system})
    messages.append({"role": "user", "content": prompt})
    return messages
