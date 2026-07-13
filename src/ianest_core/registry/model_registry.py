from __future__ import annotations

from dataclasses import dataclass

from ianest_core.config.schema import CoreConfig, DomainConfig, ModelConfig, ProfileConfig
from ianest_core.errors import ConfigValidationError, RoutingError


@dataclass(frozen=True)
class ResolvedModel:
    model: ModelConfig
    domain: DomainConfig | None
    profile: ProfileConfig


class ModelRegistry:
    def __init__(self, config: CoreConfig) -> None:
        self.config = config
        self._models = {model.id: model for model in config.models}
        self._domains = {domain.id: domain for domain in config.domains}
        self._profiles = {profile.id: profile for profile in config.profiles}

    def resolve_prompt_target(self, model_id: str | None, domain_id: str | None) -> ResolvedModel:
        if model_id:
            model = self._require_model(model_id)
            profile = self._require_profile(model.profile)
            domain = self._domains.get(domain_id or "")
            return ResolvedModel(model=model, domain=domain, profile=profile)

        if domain_id:
            domain = self._require_domain(domain_id)
            model = self._require_model(domain.preferred_model)
            profile = self._require_profile(domain.profile or model.profile)
            return ResolvedModel(model=model, domain=domain, profile=profile)

        raise RoutingError("prompt.run requires declared model or domain", "model")

    def list_models(self) -> list[ModelConfig]:
        return list(self.config.models)

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

