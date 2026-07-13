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


def test_runtime_health_declares_mcp_default_protocol() -> None:
    result = service.health(config_path=CONFIG)

    assert result["status"] == "ok"
    assert result["process"]["ok"] is True
    assert result["mcp"]["protocol_version"] == "2025-03-26"
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


@pytest.mark.skipif(importlib.util.find_spec("mcp") is None, reason="MCP extra not installed")
def test_mcp_server_exposes_tools() -> None:
    import anyio

    from ianest_core.mcp_server import create_server

    server = create_server(CONFIG)

    assert server.name == "ia_nest_core"

    async def call_prompt():
        return await server.call_tool("prompt.run", {"prompt": "hola", "domain": "general"})

    _, structured = anyio.run(call_prompt)
    assert structured["response"] == "fake response from fake_b: hola"
    assert structured["model"] == "fake_b"
