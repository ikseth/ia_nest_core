from __future__ import annotations

import json
import os
from dataclasses import replace
from pathlib import Path

from ianest_core.adapters import Event, ModelRequest
from ianest_core.cli import main
from ianest_core.config import load_config
from ianest_core.config.schema import ProfileConfig, TelemetryConfig
from ianest_core.registry import StaticAvailabilityProvider
from ianest_core.runtime import DomainRuntime, PromptRuntime, ReasoningRuntime


def test_cli_loads_dotenv_from_current_directory(tmp_path, monkeypatch, capsys) -> None:
    config_path = tmp_path / "core.yaml"
    config_path.write_text(
        """
models:
  - id: fake_a
    provider: fake
    adapter: openai_compatible
    endpoint: ${OPENAI_COMPAT_BASE_URL}
    model_name: fake-a
    capabilities: [chat]
    profile: default
domains:
  - id: general
    description: General
    preferred_model: fake_a
    fallback_models: []
    profile: default
    routing_rules: {keywords: []}
    status: active
profiles:
  - id: default
    temperature: 0.2
""".strip(),
        encoding="utf-8",
    )
    (tmp_path / ".env").write_text(
        "OPENAI_COMPAT_BASE_URL=fake://from-env\nEXISTING_URL=fake://dotenv\n",
        encoding="utf-8",
    )
    monkeypatch.chdir(tmp_path)
    monkeypatch.delenv("OPENAI_COMPAT_BASE_URL", raising=False)
    monkeypatch.setenv("EXISTING_URL", "fake://preexisting")

    exit_code = main(["--config", str(config_path), "config", "validate", "--json"])
    captured = capsys.readouterr()

    assert exit_code == 0
    assert json.loads(captured.out)["status"] == "ok"
    assert os.environ["OPENAI_COMPAT_BASE_URL"] == "fake://from-env"
    assert os.environ["EXISTING_URL"] == "fake://preexisting"


def test_domain_route_exposes_fallback_substitution(tmp_path) -> None:
    config = _config_with_tmp_telemetry(tmp_path)
    runtime = DomainRuntime(
        config,
        availability=StaticAvailabilityProvider(unavailable_models={"fake_a"}),
    )

    result = runtime.route(prompt="tengo un error", tags=["support"])

    assert result.domain == "support"
    assert result.model == "fake_b"
    assert result.substituted is True
    assert result.preferred_model == "fake_a"
    assert result.to_dict()["substituted"] is True
    assert result.to_dict()["preferred_model"] == "fake_a"


def test_profile_system_is_prepended_for_prompt_and_reasoning(tmp_path) -> None:
    config = _config_with_system(tmp_path, "Responde siempre en espanol.")
    prompt_adapter = CaptureAdapter('{"output": "ok", "done": true}')
    prompt_runtime = PromptRuntime(config)
    prompt_runtime._adapter_for = lambda model: prompt_adapter  # type: ignore[method-assign]

    prompt_runtime.run(prompt="hola", domain_id="general")

    assert prompt_adapter.requests[0][0] == {
        "role": "system",
        "content": "Responde siempre en espanol.",
    }
    assert prompt_adapter.requests[0][1]["role"] == "user"

    reasoning_adapter = CaptureAdapter('{"output": "final", "done": true}')
    reasoning_runtime = ReasoningRuntime(config, adapter=reasoning_adapter)

    reasoning_runtime.run(prompt="razona", domain_id="general")

    assert reasoning_adapter.requests[0][0] == {
        "role": "system",
        "content": "Responde siempre en espanol.",
    }
    assert reasoning_adapter.requests[0][1]["role"] == "user"


class CaptureAdapter:
    def __init__(self, text: str) -> None:
        self.text = text
        self.requests: list[list[dict[str, str]]] = []

    def stream(self, req: ModelRequest):
        self.requests.append(req.messages)
        yield Event("done", {"text": self.text, "model": "fake_b", "tokens_in": 1, "tokens_out": 1})


def _config_with_tmp_telemetry(tmp_path):
    return replace(
        load_config(Path("eval/fixtures/config.yaml")),
        telemetry=TelemetryConfig(csv_path=str(tmp_path / "trace.csv"), jsonl_path=str(tmp_path / "trace.jsonl")),
    )


def _config_with_system(tmp_path, system: str):
    config = _config_with_tmp_telemetry(tmp_path)
    profile = config.profiles[0]
    return replace(
        config,
        profiles=[ProfileConfig(id=profile.id, params=profile.params, extra=profile.extra, system=system)],
    )
