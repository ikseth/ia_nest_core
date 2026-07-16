from __future__ import annotations

from dataclasses import dataclass

from ianest_core.config.schema import CoreConfig, DomainConfig, ModelConfig, ProfileConfig
from ianest_core.errors import ConfigValidationError, ModelUnavailable, RoutingError
from ianest_core.registry.availability import AdapterAvailabilityProvider, AvailabilityProvider


@dataclass(frozen=True)
class ResolvedModel:
    model: ModelConfig
    domain: DomainConfig | None
    profile: ProfileConfig
    substituted: bool = False
    preferred_model: str = ""


class ModelRegistry:
    def __init__(self, config: CoreConfig, availability: AvailabilityProvider | None = None) -> None:
        self.config = config
        self.availability = availability or AdapterAvailabilityProvider()
        self._models = {model.id: model for model in config.models}
        self._domains = {domain.id: domain for domain in config.domains}
        self._profiles = {profile.id: profile for profile in config.profiles}

    def resolve_prompt_target(self, model_id: str | None, domain_id: str | None) -> ResolvedModel:
        if model_id:
            model = self._require_model(model_id)
            if not self.is_available(model.id):
                raise ModelUnavailable(f"model '{model.id}' is not available", "model")
            profile = self._require_profile(model.profile)
            domain = self._domains.get(domain_id or "")
            return ResolvedModel(model=model, domain=domain, profile=profile, preferred_model=model.id)

        if domain_id:
            return self.resolve_domain_model(domain_id)

        raise RoutingError("prompt.run requires declared model or domain", "model")

    def resolve_domain_model(self, domain_id: str) -> ResolvedModel:
        domain = self._require_domain(domain_id)
        model_ids = [domain.preferred_model, *domain.fallback_models]
        for model_id in model_ids:
            model = self._require_model(model_id)
            if self.is_available(model.id):
                profile = self._require_profile(domain.profile or model.profile)
                return ResolvedModel(
                    model=model,
                    domain=domain,
                    profile=profile,
                    substituted=model.id != domain.preferred_model,
                    preferred_model=domain.preferred_model,
                )
        raise ModelUnavailable(f"no available model for domain '{domain.id}'", "model")

    def list_models(self) -> list[ModelConfig]:
        return list(self.config.models)

    def list_domains(self) -> list[DomainConfig]:
        return list(self.config.domains)

    def is_available(self, model_id: str) -> bool:
        return self.availability.is_available(self._require_model(model_id))

    def model_records(self) -> list[dict[str, object]]:
        return [
            {
                "id": model.id,
                "provider": model.provider,
                "available": self.is_available(model.id),
                "capabilities": model.capabilities,
                "profile": model.profile,
            }
            for model in self.list_models()
        ]

    def domain_records(self) -> list[dict[str, object]]:
        return [
            {
                "id": domain.id,
                "description": domain.description,
                "preferred_model": domain.preferred_model,
                "fallback_models": domain.fallback_models,
                "profile": domain.profile,
                "status": domain.status,
            }
            for domain in self.list_domains()
        ]

    def profile(self, profile_id: str) -> ProfileConfig:
        return self._require_profile(profile_id)

    def _require_model(self, model_id: str) -> ModelConfig:
        model = self._models.get(model_id)
        if model is None:
            raise ConfigValidationError(f"unknown model '{model_id}'", "model")
        return model

    def _require_domain(self, domain_id: str) -> DomainConfig:
        domain = self._domains.get(domain_id)
        if domain is None:
            raise ConfigValidationError(f"unknown domain '{domain_id}'", "domain")
        return domain

    def _require_profile(self, profile_id: str) -> ProfileConfig:
        profile = self._profiles.get(profile_id)
        if profile is None:
            raise ConfigValidationError(f"unknown profile '{profile_id}'", "profile")
        return profile
