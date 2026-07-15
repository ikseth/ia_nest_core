from __future__ import annotations

import json

import pytest

from ianest_core import service
from ianest_core.cli import main
from ianest_core.config.schema import ModelConfig
from ianest_core.errors import CoreError
from ianest_core.provisioning import OllamaProvisioner, provisioner_for


class FakeProvisioner:
    def __init__(self, local_models: set[str]) -> None:
        self.local_models = local_models
        self.pulled: list[str] = []

    def list_local(self) -> set[str]:
        return self.local_models

    def pull(self, model_name: str) -> None:
        self.pulled.append(model_name)


def test_pull_models_downloads_only_missing_declared_models(tmp_path) -> None:
    config_path = _write_config(tmp_path)
    fake = FakeProvisioner({"present-model"})

    result = service.pull_models(
        config_path=config_path,
        provisioner_factory=lambda model: fake if model.provider == "ollama" else None,
    )

    assert result == {"pulled": ["missing-model"], "present": ["present-model"]}
    assert fake.pulled == ["missing-model"]


def test_model_pull_uses_declared_id_or_model_name(tmp_path, monkeypatch, capsys) -> None:
    config_path = _write_config(tmp_path)
    fake = FakeProvisioner(set())
    monkeypatch.setattr(service, "provisioner_for", lambda model: fake)

    exit_code = main(
        [
            "--config",
            str(config_path),
            "model",
            "pull",
            "present",
            "missing-model",
            "--json",
        ]
    )
    captured = capsys.readouterr()

    assert exit_code == 0
    assert json.loads(captured.out) == {"present": [], "pulled": ["present-model", "missing-model"]}
    assert fake.pulled == ["present-model", "missing-model"]


def test_pull_models_rejects_undeclared_model(tmp_path) -> None:
    config_path = _write_config(tmp_path)

    with pytest.raises(CoreError, match="modelo no declarado"):
        service.pull_models(config_path=config_path, model_references=["unknown"])


def test_pull_models_rejects_backend_without_provisioner(tmp_path) -> None:
    config_path = _write_config(tmp_path)

    with pytest.raises(CoreError, match="not supported"):
        service.pull_models(
            config_path=config_path,
            model_references=["present"],
            provisioner_factory=lambda model: None,
        )


def test_provisioner_for_selects_ollama() -> None:
    ollama_model = _model(provider="ollama", endpoint="http://example.test:11434/v1")
    other_model = _model(provider="other", endpoint="http://example.test/v1")

    provisioner = provisioner_for(ollama_model)

    assert isinstance(provisioner, OllamaProvisioner)
    assert provisioner.base == "http://example.test:11434"
    assert provisioner_for(other_model) is None


def _write_config(tmp_path) -> str:
    config_path = tmp_path / "core.yaml"
    config_path.write_text(
        """
models:
  - id: present
    provider: ollama
    adapter: openai_compatible
    endpoint: http://example.test:11434/v1
    model_name: present-model
    capabilities: [chat]
    profile: default
  - id: missing
    provider: ollama
    adapter: openai_compatible
    endpoint: http://example.test:11434/v1
    model_name: missing-model
    capabilities: [chat]
    profile: default
domains:
  - id: general
    description: General
    preferred_model: present
    fallback_models: []
    profile: default
    routing_rules: {keywords: []}
    status: active
profiles:
  - id: default
""".strip(),
        encoding="utf-8",
    )
    return str(config_path)


def _model(*, provider: str, endpoint: str) -> ModelConfig:
    return ModelConfig(
        id="model",
        provider=provider,
        adapter="openai_compatible",
        endpoint=endpoint,
        model_name="model-name",
        capabilities=["chat"],
        profile="default",
    )
