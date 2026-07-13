from __future__ import annotations

from typing import Any, Protocol

from ianest_core.identity import Identity


class MemoryPort(Protocol):
    def read_context(self, identity: Identity, hints: dict[str, Any] | None = None) -> dict[str, Any]:
        ...

    def write(self, identity: Identity, tier: str, record: dict[str, Any]) -> None:
        ...

    def record_milestone(self, identity: Identity, payload: dict[str, Any]) -> None:
        ...
