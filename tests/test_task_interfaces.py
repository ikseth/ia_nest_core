from __future__ import annotations

import importlib.util
import json

import pytest

from ianest_core import service
from ianest_core.adapters import Event
from ianest_core.cli import main


EVENTS = [
    {"type": "task_received", "data": {"prompt": "tarea"}},
    {"type": "plan_ready", "data": {"plan": [{"prompt": "s1"}]}},
    {"type": "task_done", "data": {"response": "FINAL", "stop_reason": "task_done"}},
]


def test_service_task_mode_is_forwarded_unchanged(monkeypatch) -> None:
    calls = []

    class Result:
        def to_dict(self):
            return {"response": "FINAL"}

    class Runtime:
        def __init__(self, config, availability=None):
            pass

        def run(self, **kwargs):
            calls.append(("run", kwargs))
            return Result()

        def stream(self, **kwargs):
            calls.append(("stream", kwargs))
            yield Event("task_done", {"response": "FINAL"})

    monkeypatch.setattr(service, "load_config", lambda path: object())
    monkeypatch.setattr(service, "TaskRuntime", Runtime)

    service.run_task(config_path="unused", prompt="tarea", mode="coverage")
    list(service.stream_task(config_path="unused", prompt="tarea", mode="coverage"))

    assert calls[0][1]["mode"] == "coverage"
    assert calls[1][1]["mode"] == "coverage"


def test_cli_task_run_emits_checkpoints_as_jsonl(monkeypatch, capsys) -> None:
    calls = []
    monkeypatch.setattr(service, "stream_task", lambda **kwargs: calls.append(kwargs) or iter(EVENTS))

    exit_code = main([
        "--config", "unused", "task", "run", "--prompt", "tarea",
        "--mode", "coverage", "--json",
    ])
    output = [json.loads(line) for line in capsys.readouterr().out.splitlines()]

    assert exit_code == 0
    assert [event["type"] for event in output] == ["task_received", "plan_ready", "task_done"]
    assert calls[0]["mode"] == "coverage"


def test_cli_task_run_prints_answer_chunks_incrementally(monkeypatch, capsys) -> None:
    events = [
        {"type": "task_received", "data": {"prompt": "tarea"}},
        {"type": "answer_chunk", "data": {"text": "FIRST"}},
        {"type": "coverage_updated", "data": {"completed": ["u1"]}},
        {"type": "answer_chunk", "data": {"text": "SECOND"}},
        {"type": "task_done", "data": {"response": "FIRSTSECOND"}},
    ]
    calls = []
    monkeypatch.setattr(service, "stream_task", lambda **kwargs: calls.append(kwargs) or iter(events))

    exit_code = main(["--config", "unused", "task", "run", "--prompt", "tarea"])
    output = capsys.readouterr().out

    assert exit_code == 0
    assert "FIRST" in output
    assert "SECOND" in output
    assert output.count("FIRSTSECOND") == 0
    assert calls[0]["mode"] == "pipeline"


@pytest.mark.skipif(importlib.util.find_spec("starlette") is None, reason="REST extra not installed")
def test_rest_task_run_is_sse(monkeypatch) -> None:
    import anyio
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
    calls = []
    monkeypatch.setattr(service, "stream_task", lambda **kwargs: calls.append(kwargs) or iter(EVENTS))
    app = create_app("unused")
    endpoint = next(route.endpoint for route in app.routes if route.path == "/task/run")

    async def call_task():
        response = await endpoint(Request({"prompt": "tarea", "mode": "coverage"}))
        default_response = await endpoint(Request({"prompt": "tarea"}))
        return response, default_response

    response, default_response = anyio.run(call_task)
    body = "".join(response.content)
    assert "event: task_received" in body
    assert "event: task_done" in body
    assert calls[0]["mode"] == "coverage"
    list(default_response.content)
    assert calls[1]["mode"] == "pipeline"


@pytest.mark.skipif(importlib.util.find_spec("mcp") is None, reason="MCP extra not installed")
def test_mcp_exposes_task_run(monkeypatch) -> None:
    import anyio
    from ianest_core.mcp_server import create_server

    calls = []
    monkeypatch.setattr(service, "run_task", lambda **kwargs: calls.append(kwargs) or EVENTS[-1]["data"])
    server = create_server("unused")

    async def call_task():
        return await server.call_tool("task.run", {"prompt": "tarea", "mode": "coverage"})

    _, structured = anyio.run(call_task)
    assert structured["response"] == "FINAL"
    assert calls[0]["mode"] == "coverage"

    async def call_task_default():
        return await server.call_tool("task.run", {"prompt": "tarea"})

    anyio.run(call_task_default)
    assert calls[1]["mode"] == "pipeline"
