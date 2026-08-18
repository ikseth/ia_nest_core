from __future__ import annotations

from pathlib import Path

import pytest

from ianest_core.adapters import ScriptedFakeAdapter
from ianest_core.config import load_config
from ianest_core.domain_router import DomainRouter
from ianest_core.errors import RoutingError
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


def test_router_without_config_raises_clear_error() -> None:
    config = load_config(Path("eval/fixtures/config.yaml"))
    assert config.router is None
    router = DomainRouter(
        ModelRegistry(config, availability=StaticAvailabilityProvider()),
        config,
        adapter_factory=lambda _model: pytest.fail("routing invoked an adapter"),
    )

    with pytest.raises(RoutingError) as exc:
        router.route("tengo un error en el sistema")

    assert str(exc.value) == "routing requires config.router"
    assert exc.value.field == "router"


@pytest.mark.parametrize(
    "response",
    [
        '{"domain": "codigo", "confidence": 0.91}',
        '{"domain": "codigo", "confidence": 0.91, "reason": null}',
        '{"domain": "codigo", "confidence": 0.91, "reason": ""}',
    ],
)
def test_semantic_router_supplies_missing_or_unusable_reason(response: str) -> None:
    config = load_config(Path("eval/fixtures/router.yaml"))
    router = DomainRouter(
        ModelRegistry(config, availability=StaticAvailabilityProvider()),
        config,
        adapter_factory=lambda _model: ScriptedFakeAdapter("fake_router", [response]),
    )

    result = router.route("clasifica este texto")

    assert result.domain == "codigo"
    assert result.reason == "router did not provide a reason"


def test_semantic_router_retries_once_after_invalid_response() -> None:
    config = load_config(Path("eval/fixtures/router.yaml"))
    adapter = CountingScriptedAdapter(
        "fake_router",
        [
            "respuesta no JSON",
            '{"domain": "codigo", "confidence": 0.91, "reason": "codigo"}',
            '{"domain": "general", "confidence": 0.1, "reason": "must not be used"}',
        ],
    )
    router = DomainRouter(
        ModelRegistry(config, availability=StaticAvailabilityProvider()),
        config,
        adapter_factory=lambda _model: adapter,
    )

    result = router.route("clasifica este texto")

    assert result.domain == "codigo"
    assert adapter.calls == 2


class CountingScriptedAdapter(ScriptedFakeAdapter):
    def __init__(self, model: str, responses: list[str]) -> None:
        super().__init__(model, responses)
        self.calls = 0

    def stream(self, req):
        self.calls += 1
        yield from super().stream(req)
