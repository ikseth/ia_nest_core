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
    assert result["mcp"]["protocol_version"] == expected
    assert result["backend"]["available_models"] == 2


@pytest.mark.skipif(importlib.util.find_spec("starlette") is None, reason="REST extra not installed")
def test_rest_prompt_run_and_stream_have_service_parity() -> None:
    from starlette.testclient import TestClient

    from ianest_core.rest import create_app

    expected = service.run_prompt(config_path=CONFIG, prompt="hola", domain="general")
    client = TestClient(create_app(CONFIG))

    response = client.post("/prompt/run", json={"prompt": "hola", "domain": "general"})
    assert response.status_code == 200
    assert response.json()["response"] == expected["response"]

    with client.stream("POST", "/prompt/stream", json={"prompt": "hola", "domain": "general"}) as stream:
        body = "".join(stream.iter_text())

    assert "event: token" in body
    assert "event: done" in body

    response = client.post("/reasoning/run", json={"prompt": "hola", "domain": "general"})
    assert response.status_code == 200
    assert response.json()["stop_reason"] == "max_iterations"

    with client.stream("POST", "/reasoning/stream", json={"prompt": "hola", "domain": "general"}) as stream:
        reasoning_body = "".join(stream.iter_text())

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
