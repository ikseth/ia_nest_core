from __future__ import annotations

import json
from dataclasses import dataclass
from typing import Any, Callable

from ianest_core.adapters import (
    FakeAdapter,
    ModelAdapter,
    ModelRequest,
    OpenAICompatibleAdapter,
    run_blocking,
)
from ianest_core.config.schema import CoreConfig, DomainConfig, ModelConfig
from ianest_core.errors import CoreError, RoutingError
from ianest_core.registry import ModelRegistry, ResolvedModel


@dataclass(frozen=True)
class RouteResult:
    domain: str
    model: str
    confidence: float
    reason: str
    alternatives: list[dict[str, Any]]
    resolved: ResolvedModel
    substituted: bool = False
    preferred_model: str = ""

    def to_dict(self) -> dict[str, object]:
        return {
            "domain": self.domain,
            "model": self.model,
            "confidence": self.confidence,
            "reason": self.reason,
            "alternatives": self.alternatives,
            "substituted": self.substituted,
            "preferred_model": self.preferred_model,
        }


class DomainRouter:
    def __init__(
        self,
        registry: ModelRegistry,
        config: CoreConfig,
        adapter_factory: Callable[[ModelConfig], ModelAdapter | None] | None = None,
    ) -> None:
        self.registry = registry
        self.config = config
        self.adapter_factory = adapter_factory

    def route(self, prompt: str, tags: list[str] | None = None) -> RouteResult:
        del tags
        if self.config.router is None:
            raise RoutingError("routing requires config.router", "router")
        return self._route_semantic(prompt)

    def _route_semantic(self, prompt: str) -> RouteResult:
        selected = self._default_domain()
        confidence = 0.0
        reason = "router response could not be parsed"
        alternatives: list[dict[str, Any]] = []
        try:
            decision = self._classify(prompt)
        except CoreError as exc:
            reason = f"router failed: {exc.type}"
        else:
            alternatives = decision.get("alternatives", [])
            domain_id = decision["domain"]
            matched = next(
                (domain for domain in self.registry.list_domains() if domain.id == domain_id),
                None,
            )
            if matched is None:
                reason = f"router selected unknown domain '{domain_id}'"
            else:
                selected = matched
                confidence = decision["confidence"]
                reason = decision["reason"]

        resolved = self.registry.resolve_domain_model(selected.id)
        return RouteResult(
            domain=selected.id,
            model=resolved.model.id,
            confidence=confidence,
            reason=reason,
            alternatives=alternatives,
            resolved=resolved,
            substituted=resolved.substituted,
            preferred_model=resolved.preferred_model,
        )

    def _classify(self, prompt: str) -> dict[str, Any]:
        target = self.config.router
        if target is None:
            raise RoutingError("router is not configured", "router")
        resolved = self.registry.resolve_prompt_target(target.model, target.domain)
        profile = self.registry.profile(target.profile)
        messages: list[dict[str, str]] = []
        if profile.system:
            messages.append({"role": "system", "content": profile.system})
        messages.append({"role": "user", "content": self._classification_prompt(prompt)})
        response = run_blocking(
            self._adapter_for(resolved.model),
            ModelRequest(messages=messages, params=dict(profile.params), extra=dict(profile.extra)),
        )
        decision = _parse_router_response(response.text)
        if decision is None:
            raise RoutingError("router response is not valid JSON", "router")
        return decision

    def _classification_prompt(self, prompt: str) -> str:
        catalog = [
            {"id": domain.id, "description": domain.description}
            for domain in self.registry.list_domains()
        ]
        return (
            "Classify the text into exactly one configured domain by meaning. "
            "Return only JSON with domain, confidence, reason, and optional alternatives.\n"
            f"Domain catalog: {json.dumps(catalog, ensure_ascii=False)}\n"
            f"Text to classify: {prompt}"
        )

    def _adapter_for(self, model: ModelConfig) -> ModelAdapter:
        if self.adapter_factory is not None:
            adapter = self.adapter_factory(model)
            if adapter is not None:
                return adapter
        if model.provider == "fake" or model.endpoint.startswith("fake://"):
            return FakeAdapter(model=model.id)
        return OpenAICompatibleAdapter(endpoint=model.endpoint, model_name=model.model_name)

    def _default_domain(self) -> DomainConfig:
        if self.config.default_domain is not None:
            for domain in self.registry.list_domains():
                if domain.id == self.config.default_domain:
                    return domain
            raise RoutingError(
                f"default domain '{self.config.default_domain}' is not configured",
                "default_domain",
            )
        for domain in self.registry.list_domains():
            if domain.id == "general":
                return domain
        domains = self.registry.list_domains()
        if domains:
            return domains[0]
        raise RoutingError("no domains configured", "domains")


def _parse_router_response(text: str) -> dict[str, Any] | None:
    cleaned = text.strip()
    if cleaned.startswith("```"):
        first_line_end = cleaned.find("\n")
        cleaned = cleaned[first_line_end + 1 :] if first_line_end >= 0 else ""
    if cleaned.endswith("```"):
        cleaned = cleaned[:-3].rstrip()
    object_start = cleaned.find("{")
    if object_start < 0:
        return None
    try:
        parsed, _ = json.JSONDecoder().raw_decode(cleaned[object_start:])
    except (json.JSONDecodeError, TypeError):
        return None
    if not isinstance(parsed, dict) or not isinstance(parsed.get("domain"), str):
        return None
    confidence = parsed.get("confidence")
    if isinstance(confidence, bool) or not isinstance(confidence, (int, float)):
        return None
    confidence = float(confidence)
    if not 0.0 <= confidence <= 1.0 or not isinstance(parsed.get("reason"), str):
        return None
    alternatives = parsed.get("alternatives", [])
    if not isinstance(alternatives, list):
        alternatives = []
    return {
        "domain": parsed["domain"],
        "confidence": confidence,
        "reason": parsed["reason"],
        "alternatives": [dict(item) for item in alternatives if isinstance(item, dict)],
    }
