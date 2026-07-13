from __future__ import annotations

import json
from typing import Protocol
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen

from ianest_core.config.schema import ModelConfig


class AvailabilityProvider(Protocol):
    def is_available(self, model: ModelConfig) -> bool:
        ...


class StaticAvailabilityProvider:
    def __init__(self, unavailable_models: set[str] | None = None) -> None:
        self.unavailable_models = unavailable_models or set()

    def is_available(self, model: ModelConfig) -> bool:
        return model.id not in self.unavailable_models


class AdapterAvailabilityProvider:
    def is_available(self, model: ModelConfig) -> bool:
        if model.provider == "fake" or model.endpoint.startswith("fake://"):
            return True
        if not model.endpoint:
            return False
        return _probe_openai_models(model)


def _probe_openai_models(model: ModelConfig) -> bool:
    url = _models_url(model.endpoint)
    request = Request(url, headers={"Accept": "application/json"}, method="GET")
    try:
        with urlopen(request, timeout=10) as response:
            data = json.loads(response.read().decode("utf-8"))
    except (HTTPError, URLError, TimeoutError, OSError, json.JSONDecodeError):
        return False
    models = data.get("data", [])
    if not models:
        return True
    return any(item.get("id") == model.model_name for item in models if isinstance(item, dict))


def _models_url(endpoint: str) -> str:
    clean = endpoint.rstrip("/")
    if clean.endswith("/models"):
        return clean
    return f"{clean}/models" if clean.endswith("/v1") else f"{clean}/v1/models"
