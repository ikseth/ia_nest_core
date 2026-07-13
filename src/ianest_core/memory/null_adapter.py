from __future__ import annotations

from typing import Any

from ianest_core.identity import Identity


class NullMemoryAdapter:
    def read_context(self, identity: Identity, hints: dict[str, Any] | None = None) -> dict[str, Any]:
        return {}

    def write(self, identity: Identity, tier: str, record: dict[str, Any]) -> None:
        return None

    def record_milestone(self, identity: Identity, payload: dict[str, Any]) -> None:
        return None
