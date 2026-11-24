from __future__ import annotations

from dataclasses import dataclass

from ianest_core.errors import ConfigValidationError


PROFILE_ADULT = "adult"
PROFILE_RESTRICTED = "restricted"
# `child` es el nombre antiguo de `restricted` (ADR 0055, D5; meta ADR 0019):
# se acepta una version y se normaliza.
LEGACY_PROFILE_ALIASES = {"child": PROFILE_RESTRICTED}
INTERLOCUTOR_PROFILES = frozenset({PROFILE_ADULT, PROFILE_RESTRICTED})
ACCEPTED_PROFILE_NAMES = INTERLOCUTOR_PROFILES | frozenset(LEGACY_PROFILE_ALIASES)


def normalize_profile(value: str) -> str:
    return LEGACY_PROFILE_ALIASES.get(value, value)


@dataclass(frozen=True)
class Identity:
    user_id: str = ""
    service: str = ""
    session_id: str = ""
    domain_tag: str = ""
    namespace: str = ""
    interlocutor_profile: str = ""

    def __post_init__(self) -> None:
        if self.interlocutor_profile and self.interlocutor_profile not in ACCEPTED_PROFILE_NAMES:
            raise ConfigValidationError(
                "interlocutor_profile must be adult or restricted",
                "interlocutor_profile",
            )
        object.__setattr__(
            self, "interlocutor_profile", normalize_profile(self.interlocutor_profile)
        )

    @classmethod
    def from_defaults(
        cls,
        defaults: dict[str, str],
        override: dict[str, str] | None = None,
    ) -> "Identity":
        data = {**defaults, **(override or {})}
        return cls(
            user_id=str(data.get("user_id", "")),
            service=str(data.get("service", "")),
            session_id=str(data.get("session_id", "")),
            domain_tag=str(data.get("domain_tag", "")),
            namespace=str(data.get("namespace", "")),
            interlocutor_profile=str(data.get("interlocutor_profile", "")),
        )

    def to_dict(self) -> dict[str, str]:
        return {
            "user_id": self.user_id,
            "service": self.service,
            "session_id": self.session_id,
            "domain_tag": self.domain_tag,
            "namespace": self.namespace,
            "interlocutor_profile": self.interlocutor_profile,
        }

