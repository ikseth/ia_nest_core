from __future__ import annotations

from dataclasses import dataclass

from ianest_core.config.schema import DomainConfig
from ianest_core.errors import RoutingError
from ianest_core.registry import ModelRegistry, ResolvedModel


@dataclass(frozen=True)
class RouteResult:
    domain: str
    model: str
    confidence: float
    reason: str
    alternatives: list[dict[str, str | float]]
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
    def __init__(self, registry: ModelRegistry) -> None:
        self.registry = registry

    def route(self, prompt: str, tags: list[str] | None = None) -> RouteResult:
        tags = tags or []
        matches = self._matches(prompt, tags)
        selected = matches[0][0] if matches else self._default_domain()
        reason = matches[0][1] if matches else "default domain"
        confidence = 1.0 if matches else 0.0
        resolved = self.registry.resolve_domain_model(selected.id)
        alternatives = [
            {"domain": domain.id, "confidence": 1.0, "reason": match_reason}
            for domain, match_reason in matches[1:]
        ]
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

    def _matches(self, prompt: str, tags: list[str]) -> list[tuple[DomainConfig, str]]:
        prompt_text = prompt.lower()
        tag_set = {tag.lower() for tag in tags}
        matches: list[tuple[DomainConfig, str]] = []
        for domain in self.registry.list_domains():
            rules = domain.routing_rules
            for keyword in rules.get("keywords", []):
                if str(keyword).lower() in prompt_text:
                    matches.append((domain, f"keyword:{keyword}"))
                    break
            else:
                rule_tags = {str(tag).lower() for tag in rules.get("tags", [])}
                if rule_tags and rule_tags.intersection(tag_set):
                    matches.append((domain, "tag match"))
        return matches

    def _default_domain(self) -> DomainConfig:
        for domain in self.registry.list_domains():
            if domain.id == "general":
                return domain
        domains = self.registry.list_domains()
        if domains:
            return domains[0]
        raise RoutingError("no domains configured", "domains")
