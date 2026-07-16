from __future__ import annotations

from dataclasses import replace
from pathlib import Path

import pytest

from ianest_core.config import load_config, validate_config_dict
from ianest_core.config.schema import TelemetryConfig
from ianest_core.domain_router import DomainRouter
from ianest_core.errors import ConfigValidationError, ModelUnavailable
from ianest_core.evaluation import run_eval
from ianest_core.registry import ModelRegistry, StaticAvailabilityProvider
from ianest_core.runtime import PromptRuntime
from ianest_core.telemetry.trace import ROTATE_SIZE_BYTES, TelemetryWriter
from ianest_core.identity import Identity


def test_domain_router_matches_keyword_and_default() -> None:
    config = load_config(Path("eval/fixtures/config.yaml"))
    router = DomainRouter(ModelRegistry(config, availability=StaticAvailabilityProvider()))

    support = router.route("tengo un error en el sistema")
    general = router.route("hola, buenos dias")

    assert support.domain == "support"
    assert support.model == "fake_a"
    assert support.reason == "keyword:error"
    assert general.domain == "general"
    assert general.model == "fake_b"
    assert general.reason == "default domain"


def test_prompt_runtime_uses_fallback_and_traces_substitution(tmp_path) -> None:
    config = _config_with_tmp_telemetry(tmp_path)
    runtime = PromptRuntime(
        config,
        availability=StaticAvailabilityProvider(unavailable_models={"fake_a"}),
    )

    result = runtime.run(prompt="reporto un fallo", domain_id="support", request_id="fallback")

    assert result.model == "fake_b"
    assert result.trace["substituted"] is True
    assert result.trace["preferred_model"] == "fake_a"

    csv_text = (tmp_path / "trace.csv").read_text(encoding="utf-8")
    assert ";route;" in csv_text


def test_prompt_runtime_raises_model_unavailable_when_chain_is_down(tmp_path) -> None:
    config = _config_with_tmp_telemetry(tmp_path)
    runtime = PromptRuntime(
        config,
        availability=StaticAvailabilityProvider(unavailable_models={"fake_a", "fake_b"}),
    )

    with pytest.raises(ModelUnavailable) as exc:
        runtime.run(prompt="reporto un fallo", domain_id="support")

    assert exc.value.type == "ModelUnavailable"
    assert exc.value.field == "model"


def test_config_validate_detects_dangling_reference() -> None:
    raw = {
        "models": [
            {
                "id": "only_model",
                "provider": "fake",
                "adapter": "openai_compatible",
                "endpoint": "fake://x",
                "model_name": "x",
                "capabilities": ["chat"],
                "profile": "default",
            }
        ],
        "domains": [
            {
                "id": "broken",
                "description": "Dominio con referencia colgante",
                "preferred_model": "does_not_exist",
                "fallback_models": [],
                "profile": "default",
                "routing_rules": {"keywords": []},
                "status": "active",
            }
        ],
        "profiles": [{"id": "default", "temperature": 0.2}],
    }

    with pytest.raises(ConfigValidationError) as exc:
        validate_config_dict(raw)

    assert exc.value.field == "preferred_model"


def test_eval_conformance_digest_is_stable() -> None:
    first = run_eval(track="conformance")
    second = run_eval(track="conformance")

    assert first["totals"]["conformance"] == {"pass": 23, "fail": 0}
    assert second["totals"]["conformance"] == {"pass": 22, "fail": 0}
    assert first["conformance_digest"] == second["conformance_digest"]
    assert first["conformance_digest"] == "1d405c95660947206a0be19a6f8ef8ecf92874a7718f3dd10348ab0fb040263b"


def test_telemetry_rotates_by_size(tmp_path) -> None:
    csv_path = tmp_path / "trace.csv"
    csv_path.write_text("x" * ROTATE_SIZE_BYTES, encoding="utf-8")
    writer = TelemetryWriter(
        TelemetryConfig(csv_path=str(csv_path), jsonl_path=str(tmp_path / "trace.jsonl"), rotation="size")
    )

    writer.record(
        request_id="rotate",
        event="done",
        capability="prompt.run",
        identity=Identity(user_id="u1", service="local_cli"),
    )

    rotated = list(tmp_path.glob("trace.csv.*"))
    assert rotated
    assert csv_path.exists()


def _config_with_tmp_telemetry(tmp_path):
    return replace(
        load_config(Path("eval/fixtures/config.yaml")),
        telemetry=TelemetryConfig(csv_path=str(tmp_path / "trace.csv"), jsonl_path=str(tmp_path / "trace.jsonl")),
    )
