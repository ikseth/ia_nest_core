from __future__ import annotations

import importlib.util
import json

import pytest

from ianest_core import service
from ianest_core.cli import main

CONFIG = "eval/fixtures/config.yaml"


def test_service_prompt_matches_cli_json(capsys) -> None:
    service_result = service.run_prompt(
        config_path=CONFIG,
        prompt="hola",
        domain="general",
        identity={"user_id": "u1", "service": "local_cli"},
    )

    exit_code = main(
        [
            "--config",
            CONFIG,
            "prompt",
            "run",
            "--prompt",
            "hola",
            "--domain",
            "general",
            "--user-id",
            "u1",
            "--service",
            "local_cli",
            "--json",
        ]
    )
    captured = capsys.readouterr()
    cli_result = json.loads(captured.out)

    assert exit_code == 0
    assert cli_result["response"] == service_result["response"]
    assert cli_result["model"] == service_result["model"]
    assert cli_result["domain"] == service_result["domain"]


def test_service_reasoning_matches_cli_json(capsys) -> None:
    service_result = service.run_reasoning(config_path=CONFIG, prompt="hola", domain="general")

    exit_code = main(
        [
            "--config",
            CONFIG,
            "reasoning",
            "run",
            "--prompt",
            "hola",
            "--domain",
            "general",
            "--json",
        ]
    )
    captured = capsys.readouterr()
    cli_result = json.loads(captured.out)

    assert exit_code == 0
    assert cli_result["output"] == service_result["output"]
    assert cli_result["model"] == service_result["model"]
    assert cli_result["domain"] == service_result["domain"]


def test_runtime_health_declares_mcp_default_protocol() -> None:
    result = service.health(config_path=CONFIG)
    try:
        from mcp.types import DEFAULT_NEGOTIATED_VERSION
    except ImportError:
        expected = "2025-03-26"
    else:
        expected = DEFAULT_NEGOTIATED_VERSION

    assert result["status"] == "ok"
    assert result["process"]["ok"] is True
    assert result["runtime"]["python"]
    assert result["runtime"]["platform"]
    assert result["mcp"]["protocol_version"] == expected
    assert result["backend"]["available_models"] == 2


def test_runtime_detect_reports_local_gpu_best_effort() -> None:
    result = service.detect_runtime(config_path=CONFIG)

    assert result["status"] == "ok"
    assert "available" in result["gpu"]
    assert "gpus" in result["gpu"]
    assert result["backend"]["scope"] == "configured_models"


@pytest.mark.skipif(importlib.util.find_spec("starlette") is None, reason="REST extra not installed")
def test_rest_prompt_run_and_stream_have_service_parity(monkeypatch) -> None:
    import anyio
    import json
    import starlette.responses

    from ianest_core.rest import create_app

    class Request:
        def __init__(self, payload):
            self.payload = payload

        async def json(self):
            return self.payload

    class StreamingResponse:
        def __init__(self, content, media_type):
            self.content = content
            self.media_type = media_type

    monkeypatch.setattr(starlette.responses, "StreamingResponse", StreamingResponse)
    expected = service.run_prompt(config_path=CONFIG, prompt="hola", domain="general")
    app = create_app(CONFIG)
    endpoints = {route.path: route.endpoint for route in app.routes}

    async def call_endpoints():
        prompt_response = await endpoints["/prompt/run"](
            Request({"prompt": "hola", "domain": "general"})
        )
        prompt_stream = await endpoints["/prompt/stream"](
            Request({"prompt": "hola", "domain": "general"})
        )
        reasoning_response = await endpoints["/reasoning/run"](
            Request({"prompt": "hola", "domain": "general"})
        )
        reasoning_stream = await endpoints["/reasoning/stream"](
            Request({"prompt": "hola", "domain": "general"})
        )
        return prompt_response, prompt_stream, reasoning_response, reasoning_stream

    response, stream, reasoning_response, reasoning_stream = anyio.run(call_endpoints)
    assert json.loads(response.body)["response"] == expected["response"]
    prompt_body = "".join(stream.content)
    assert "event: token" in prompt_body
    assert "event: done" in prompt_body
    assert json.loads(reasoning_response.body)["stop_reason"] == "max_iterations"
    reasoning_body = "".join(reasoning_stream.content)
    assert "event: step" in reasoning_body
    assert "event: done" in reasoning_body


@pytest.mark.skipif(importlib.util.find_spec("mcp") is None, reason="MCP extra not installed")
def test_mcp_server_exposes_tools() -> None:
    import anyio

    from ianest_core.mcp_server import create_server

    server = create_server(CONFIG)

    assert server.name == "ia_nest_core"

    async def call_tools():
        prompt_result = await server.call_tool("prompt.run", {"prompt": "hola", "domain": "general"})
        reasoning_result = await server.call_tool("reasoning.run", {"prompt": "hola", "domain": "general"})
        return prompt_result, reasoning_result

    (_, structured), (_, reasoning_structured) = anyio.run(call_tools)
    assert structured["response"] == "fake response from fake_b: hola"
    assert structured["model"] == "fake_b"
    assert reasoning_structured["stop_reason"] == "max_iterations"
