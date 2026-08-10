from __future__ import annotations

from pathlib import Path

import pytest

from ianest_core.adapters import ScriptedFakeAdapter
from ianest_core.config import load_config
from ianest_core.domain_router import DomainRouter
from ianest_core.registry import ModelRegistry, StaticAvailabilityProvider


@pytest.mark.parametrize(
    ("response", "expected_domain", "expected_confidence"),
    [
        (
            '{"domain": "codigo", "confidence": 0.91, "reason": "codigo"}',
            "codigo",
            0.91,
        ),
        (
            '```json\n{"domain": "humanidades", "confidence": 0.82, "reason": "texto"}\n```',
            "humanidades",
            0.82,
        ),
        (
            '{"domain": "inventado", "confidence": 0.8, "reason": "desconocido"}',
            "general",
            0.0,
        ),
        ("respuesta sin json", "general", 0.0),
    ],
)
def test_semantic_router_parses_tolerantly_and_falls_back(
    response: str,
    expected_domain: str,
    expected_confidence: float,
) -> None:
    config = load_config(Path("eval/fixtures/router.yaml"))
    adapter = ScriptedFakeAdapter("fake_router", [response])
    router = DomainRouter(
        ModelRegistry(config, availability=StaticAvailabilityProvider()),
        config,
        adapter_factory=lambda _model: adapter,
    )

    result = router.route("clasifica este texto")

    assert result.domain == expected_domain
    assert result.confidence == expected_confidence


def test_router_without_config_keeps_keyword_routing() -> None:
    config = load_config(Path("eval/fixtures/config.yaml"))
    assert config.router is None
    router = DomainRouter(
        ModelRegistry(config, availability=StaticAvailabilityProvider()),
        config,
        adapter_factory=lambda _model: pytest.fail("keyword routing invoked an adapter"),
    )

    result = router.route("tengo un error en el sistema")

    assert result.domain == "support"
    assert result.confidence == 1.0
    assert result.reason == "keyword:error"
