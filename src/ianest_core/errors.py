from __future__ import annotations

from dataclasses import dataclass


@dataclass
class CoreError(Exception):
    type: str
    message: str
    field: str | None = None

    def __str__(self) -> str:
        return self.message

    def to_dict(self) -> dict[str, str | None]:
        return {"type": self.type, "message": self.message, "field": self.field}


class ModelUnavailable(CoreError):
    def __init__(self, message: str, field: str | None = None) -> None:
        super().__init__("ModelUnavailable", message, field)


class ConfigValidationError(CoreError):
    def __init__(self, message: str, field: str | None = None) -> None:
        super().__init__("ConfigValidationError", message, field)


class ConfigError(CoreError):
    def __init__(self, message: str, field: str | None = None) -> None:
        super().__init__("ConfigError", message, field)


class AdapterError(CoreError):
    def __init__(self, message: str, field: str | None = None) -> None:
        super().__init__("AdapterError", message, field)


class RoutingError(CoreError):
    def __init__(self, message: str, field: str | None = None) -> None:
        super().__init__("RoutingError", message, field)
