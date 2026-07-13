from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class Identity:
    user_id: str = ""
    service: str = ""
    session_id: str = ""
    domain_tag: str = ""
    namespace: str = ""

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
        )

    def to_dict(self) -> dict[str, str]:
        return {
            "user_id": self.user_id,
            "service": self.service,
            "session_id": self.session_id,
            "domain_tag": self.domain_tag,
            "namespace": self.namespace,
        }

