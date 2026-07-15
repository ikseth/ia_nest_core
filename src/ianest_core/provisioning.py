from __future__ import annotations

import json
from typing import Protocol
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen

from ianest_core.config.schema import ModelConfig
from ianest_core.errors import CoreError


class Provisioner(Protocol):
    def list_local(self) -> set[str]:
        ...

    def pull(self, model_name: str) -> None:
        ...


class OllamaProvisioner:
    def __init__(self, endpoint: str) -> None:
        self.base = _ollama_base(endpoint)

    def list_local(self) -> set[str]:
        payload = self._request_json(f"{self.base}/api/tags")
        models = payload.get("models", [])
        if not isinstance(models, list):
            raise CoreError("ProvisioningError", "invalid response from Ollama tags API", "endpoint")
        return {str(model["name"]) for model in models if isinstance(model, dict) and model.get("name")}

    def pull(self, model_name: str) -> None:
        body = json.dumps({"name": model_name}).encode("utf-8")
        request = Request(
            f"{self.base}/api/pull",
            data=body,
            headers={"Content-Type": "application/json"},
            method="POST",
        )
        try:
            with urlopen(request, timeout=120) as response:
                for raw_line in response:
                    line = raw_line.decode("utf-8").strip()
                    if not line:
                        continue
                    payload = json.loads(line)
                    if payload.get("error"):
                        raise CoreError("ProvisioningError", str(payload["error"]), "model")
                    if payload.get("status") == "success":
                        return
        except CoreError:
            raise
        except (HTTPError, URLError, TimeoutError, OSError, json.JSONDecodeError) as exc:
            raise CoreError("ProvisioningError", f"Ollama pull failed: {exc}", "model") from exc
        raise CoreError("ProvisioningError", f"Ollama pull did not complete for '{model_name}'", "model")

    def _request_json(self, url: str) -> dict[str, object]:
        try:
            with urlopen(url, timeout=30) as response:
                payload = json.load(response)
        except (HTTPError, URLError, TimeoutError, OSError, json.JSONDecodeError) as exc:
            raise CoreError("ProvisioningError", f"Ollama request failed: {exc}", "endpoint") from exc
        if not isinstance(payload, dict):
            raise CoreError("ProvisioningError", "invalid response from Ollama API", "endpoint")
        return payload


def provisioner_for(model: ModelConfig) -> Provisioner | None:
    if model.provider == "ollama":
        return OllamaProvisioner(model.endpoint)
    return None


def _ollama_base(endpoint: str) -> str:
    base = endpoint.rstrip("/")
    return base[:-3] if base.endswith("/v1") else base
