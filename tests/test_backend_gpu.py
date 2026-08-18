from __future__ import annotations

import importlib.util
import json

import pytest

from ianest_core import service
from ianest_core.cli import main


CONFIG = "eval/fixtures/backend_gpu.yaml"
LOADED = [{"name": "fake-a", "size": 100, "size_vram": 100}]


class _Probe:
    def __init__(self, loaded=None) -> None:
        self.loaded = LOADED if loaded is None else loaded

    def probe_gpu(self):
        return self.loaded


def _factory(_model):
    return _Probe()


def test_backend_gpu_does_not_publish_endpoint_url() -> None:
    result = service.health(config_path=CONFIG, provisioner_factory=_factory)

    serialized = json.dumps(result["backend"]["gpu"], sort_keys=True)
    assert "backend-uno" not in serialized
    assert "http://" not in serialized
    assert "https://" not in serialized


def test_local_gpu_and_backend_gpu_are_independent() -> None:
    result = service.health(
        config_path=CONFIG,
        provisioner_factory=_factory,
        gpu_status_factory=lambda: {"available": False, "detail": "injected", "gpus": []},
    )

    assert result["gpu"]["available"] is False
    assert result["backend"]["gpu"][0]["status"] == "in_use"


def test_backend_gpu_probe_is_not_called_by_prompt_or_task(monkeypatch) -> None:
    def forbidden(_model):
        pytest.fail("backend GPU probe factory entered inference path")

    monkeypatch.setattr(service, "provisioner_for", forbidden)

    service.run_prompt(
        config_path="eval/fixtures/config.yaml",
        prompt="hola",
        domain="general",
    )
    service.run_task(
        config_path="eval/fixtures/orchestration.yaml",
        prompt="tarea",
    )


@pytest.mark.skipif(
    importlib.util.find_spec("starlette") is None or importlib.util.find_spec("mcp") is None,
    reason="interface extras not installed",
)
def test_backend_gpu_has_cli_rest_mcp_parity(monkeypatch, capsys) -> None:
    import anyio

    from ianest_core.mcp_server import create_server
    from ianest_core.rest import create_app

    expected = service.health(config_path=CONFIG, provisioner_factory=_factory)
    monkeypatch.setattr(service, "health", lambda **_kwargs: expected)

    assert main(["--config", CONFIG, "runtime", "health", "--json"]) == 0
    cli_result = json.loads(capsys.readouterr().out)

    app = create_app(CONFIG)
    rest_endpoint = next(route.endpoint for route in app.routes if route.path == "/runtime/health")

    async def call_interfaces():
        rest_response = await rest_endpoint(object())
        _, mcp_result = await create_server(CONFIG).call_tool("runtime.health", {})
        return json.loads(rest_response.body), mcp_result

    rest_result, mcp_result = anyio.run(call_interfaces)
    assert cli_result["backend"]["gpu"] == expected["backend"]["gpu"]
    assert rest_result["backend"]["gpu"] == expected["backend"]["gpu"]
    assert mcp_result["backend"]["gpu"] == expected["backend"]["gpu"]


def test_runtime_detect_and_health_publish_same_backend_gpu() -> None:
    health = service.health(config_path=CONFIG, provisioner_factory=_factory)
    detected = service.detect_runtime(config_path=CONFIG, provisioner_factory=_factory)

    assert detected["backend"]["gpu"] == health["backend"]["gpu"]


@pytest.mark.parametrize(
    "factory",
    [
        lambda _model: (_ for _ in ()).throw(OSError("factory failed")),
        lambda _model: _Probe([{"name": "broken", "size": 100}]),
    ],
)
def test_backend_gpu_probe_failures_degrade_to_unreachable(factory) -> None:
    result = service.health(config_path=CONFIG, provisioner_factory=factory)

    assert result["status"] == "ok"
    assert result["backend"]["gpu"][0] == {
        "models": ["ollama_a", "ollama_b"],
        "reported_by": None,
        "status": "unknown",
        "models_loaded": 0,
        "reason": "backend_unreachable",
    }
