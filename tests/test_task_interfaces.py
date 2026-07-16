from __future__ import annotations

import importlib.util
import json

import pytest

from ianest_core import service
from ianest_core.cli import main


EVENTS = [
    {"type": "task_received", "data": {"prompt": "tarea"}},
    {"type": "plan_ready", "data": {"plan": [{"prompt": "s1"}]}},
    {"type": "task_done", "data": {"response": "FINAL", "stop_reason": "task_done"}},
]


def test_cli_task_run_emits_checkpoints_as_jsonl(monkeypatch, capsys) -> None:
    monkeypatch.setattr(service, "stream_task", lambda **kwargs: iter(EVENTS))

    exit_code = main(["--config", "unused", "task", "run", "--prompt", "tarea", "--json"])
    output = [json.loads(line) for line in capsys.readouterr().out.splitlines()]

    assert exit_code == 0
    assert [event["type"] for event in output] == ["task_received", "plan_ready", "task_done"]


@pytest.mark.skipif(importlib.util.find_spec("starlette") is None, reason="REST extra not installed")
def test_rest_task_run_is_sse(monkeypatch) -> None:
    from starlette.testclient import TestClient
    from ianest_core.rest import create_app

    monkeypatch.setattr(service, "stream_task", lambda **kwargs: iter(EVENTS))
    client = TestClient(create_app("unused"))

    with client.stream("POST", "/task/run", json={"prompt": "tarea"}) as response:
        body = "".join(response.iter_text())

    assert response.status_code == 200
    assert "event: task_received" in body
    assert "event: task_done" in body


@pytest.mark.skipif(importlib.util.find_spec("mcp") is None, reason="MCP extra not installed")
def test_mcp_exposes_task_run(monkeypatch) -> None:
    import anyio
    from ianest_core.mcp_server import create_server

    monkeypatch.setattr(service, "run_task", lambda **kwargs: EVENTS[-1]["data"])
    server = create_server("unused")

    async def call_task():
        return await server.call_tool("task.run", {"prompt": "tarea"})

    _, structured = anyio.run(call_task)
    assert structured["response"] == "FINAL"
