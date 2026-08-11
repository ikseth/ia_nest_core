from __future__ import annotations

import importlib.util
import json

import pytest

from ianest_core import service
from ianest_core.adapters import Event
from ianest_core.cli import main


EVENTS = [
    {"type": "task_received", "data": {"prompt": "tarea"}},
    {
        "type": "plan_ready",
        "data": {
            "plan": [{"prompt": "s1"}],
            "requirements": [{"id": "r1", "text": "resolver"}],
            "plan_attempts": 1,
            "requirements_covered": True,
            "uncovered_requirements": [],
        },
    },
    {
        "type": "task_done",
        "data": {
            "response": "FINAL",
            "stop_reason": "task_done",
            "requirements_covered": True,
            "uncovered_requirements": [],
            "plan_attempts": 1,
            "evaluation_attempts": 1,
            "degradations": [],
        },
    },
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
    captured = capsys.readouterr()
    output = [json.loads(line) for line in captured.out.splitlines()]

    assert exit_code == 0
    assert [event["type"] for event in output] == ["task_received", "plan_ready", "task_done"]
    assert captured.err == ""
    assert calls[0]["mode"] == "coverage"


def test_cli_task_run_separates_coverage_answer_and_progress(monkeypatch, capsys) -> None:
    events = [
        {"type": "task_received", "data": {"prompt": "tarea"}},
        {"type": "answer_chunk", "data": {"text": " FIRST\n"}},
        {"type": "coverage_updated", "data": {"completed": ["u1"]}},
        {"type": "answer_chunk", "data": {"text": "\nSECOND "}},
        {"type": "task_done", "data": {"response": "FIRST\n\nSECOND"}},
    ]
    calls = []
    monkeypatch.setattr(service, "stream_task", lambda **kwargs: calls.append(kwargs) or iter(events))

    exit_code = main([
        "--config", "unused", "task", "run", "--prompt", "tarea", "--mode", "coverage",
    ])
    captured = capsys.readouterr()

    assert exit_code == 0
    assert captured.out == "FIRST\n\nSECOND"
    assert "Tarea recibida" in captured.err
    assert "Cobertura actualizada" in captured.err
    assert "task_received" not in captured.out
    assert "coverage_updated" not in captured.out
    assert captured.out.count("FIRST\n\nSECOND") == 1
    assert calls[0]["mode"] == "coverage"


@pytest.mark.parametrize("verbose", [False, True])
def test_cli_task_run_quiet_suppresses_progress(monkeypatch, capsys, verbose) -> None:
    events = [
        {"type": "task_received", "data": {"prompt": "tarea"}},
        {"type": "answer_chunk", "data": {"text": "FIRST"}},
        {"type": "coverage_updated", "data": {"completed": ["u1"], "pending": []}},
        {"type": "task_done", "data": {"response": "FIRST"}},
    ]
    monkeypatch.setattr(service, "stream_task", lambda **kwargs: iter(events))

    argv = [
        "--config", "unused", "task", "run", "--prompt", "tarea",
        "--mode", "coverage", "--quiet",
    ]
    if verbose:
        argv.append("--verbose")
    exit_code = main(argv)
    captured = capsys.readouterr()

    assert exit_code == 0
    assert captured.out == "FIRST"
    assert captured.err == ""


def test_cli_task_run_limit_stop_returns_error_and_preserves_partial_response(monkeypatch, capsys) -> None:
    events = [
        {"type": "combine_ready", "data": {"response": "PARCIAL"}},
        {"type": "task_done", "data": {"response": "PARCIAL", "stop_reason": "max_iterations"}},
    ]
    monkeypatch.setattr(service, "stream_task", lambda **kwargs: iter(events))

    exit_code = main(["--config", "unused", "task", "run", "--prompt", "tarea"])
    captured = capsys.readouterr()

    assert exit_code == 1
    assert captured.out == "PARCIAL\n"
    assert captured.err == (
        "Respuesta preparada\n"
        "Tarea cortada: max_iterations. Se devuelve lo producido hasta el corte.\n"
    )


def test_cli_task_run_warns_for_each_degradation_without_failing(monkeypatch, capsys) -> None:
    events = [{
        "type": "task_done",
        "data": {
            "response": "FINAL",
            "stop_reason": "task_done",
            "degradations": [
                {"stage": "plan", "reason": "unparseable_shape", "action": "single_subtask"},
                {
                    "stage": "evaluate",
                    "reason": "undecipherable_decision",
                    "action": "assume_done",
                },
            ],
        },
    }]
    monkeypatch.setattr(service, "stream_task", lambda **kwargs: iter(events))

    exit_code = main([
        "--config", "unused", "task", "run", "--prompt", "tarea", "--quiet",
    ])
    captured = capsys.readouterr()

    assert exit_code == 0
    assert captured.out == "FINAL\n"
    assert captured.err == (
        "Tarea degradada: plan (unparseable_shape -> single_subtask).\n"
        "Tarea degradada: evaluate (undecipherable_decision -> assume_done).\n"
    )


@pytest.mark.parametrize("verbose", [False, True])
def test_cli_task_run_quiet_does_not_suppress_limit_stop(monkeypatch, capsys, verbose) -> None:
    events = [{"type": "task_done", "data": {"response": "", "stop_reason": "max_subtasks"}}]
    monkeypatch.setattr(service, "stream_task", lambda **kwargs: iter(events))

    argv = ["--config", "unused", "task", "run", "--prompt", "tarea", "--quiet"]
    if verbose:
        argv.append("--verbose")
    exit_code = main(argv)
    captured = capsys.readouterr()

    assert exit_code == 1
    assert captured.out == "\n"
    assert captured.err == "Tarea cortada: max_subtasks. No se produjo respuesta.\n"


def test_cli_task_run_json_does_not_suppress_limit_stop(monkeypatch, capsys) -> None:
    events = [{"type": "task_done", "data": {"response": "", "stop_reason": "max_subtasks"}}]
    monkeypatch.setattr(service, "stream_task", lambda **kwargs: iter(events))

    exit_code = main([
        "--config", "unused", "task", "run", "--prompt", "tarea", "--json",
    ])
    captured = capsys.readouterr()

    assert exit_code == 1
    assert [json.loads(line) for line in captured.out.splitlines()] == events
    assert captured.err == "Tarea cortada: max_subtasks. No se produjo respuesta.\n"


def test_cli_task_run_empty_combination_does_not_claim_response_is_ready(monkeypatch, capsys) -> None:
    events = [
        {"type": "combine_ready", "data": {"response": ""}},
        {"type": "task_done", "data": {"response": "", "stop_reason": "max_subtasks"}},
    ]
    monkeypatch.setattr(service, "stream_task", lambda **kwargs: iter(events))

    exit_code = main(["--config", "unused", "task", "run", "--prompt", "tarea"])
    captured = capsys.readouterr()

    assert exit_code == 1
    assert "Combinacion sin respuesta" in captured.err
    assert "Respuesta preparada" not in captured.err


def test_cli_task_pipeline_prints_final_response_once(monkeypatch, capsys) -> None:
    monkeypatch.setattr(service, "stream_task", lambda **kwargs: iter(EVENTS))

    exit_code = main(["--config", "unused", "task", "run", "--prompt", "tarea"])
    captured = capsys.readouterr()

    assert exit_code == 0
    assert captured.out == "FINAL\n"
    assert "Tarea recibida" in captured.err
    assert "Plan listo" in captured.err


def test_cli_task_run_default_progress_is_concise(monkeypatch, capsys) -> None:
    monkeypatch.setattr(service, "stream_task", lambda **kwargs: iter(EVENTS))

    exit_code = main(["--config", "unused", "task", "run", "--prompt", "tarea"])
    captured = capsys.readouterr()

    assert exit_code == 0
    assert captured.err == "Tarea recibida\nPlan listo: 1 unidades\n"


def test_cli_task_run_verbose_renders_subtask_and_iteration_details(monkeypatch, capsys) -> None:
    events = [
        {"type": "task_received", "data": {"prompt": "tarea"}},
        {"type": "plan_ready", "data": {"plan": [{"prompt": "s1"}]}},
        {
            "type": "subtask_done",
            "data": {"index": 2, "iteration": 3, "domain": "analysis", "model": "local_llama"},
        },
        {"type": "iteration_end", "data": {"iteration": 3, "decision": "combine"}},
        {"type": "combine_ready", "data": {"response": "FINAL"}},
        {"type": "task_done", "data": {"response": "FINAL"}},
    ]
    monkeypatch.setattr(service, "stream_task", lambda **kwargs: iter(events))

    exit_code = main(["--config", "unused", "task", "run", "--prompt", "tarea", "--verbose"])
    captured = capsys.readouterr()

    assert exit_code == 0
    assert captured.err == (
        "Tarea recibida\n"
        "Plan: 1 subtareas\n"
        "  subtarea 2 (iter 3) -> analysis / local_llama\n"
        "Iteracion 3: combine\n"
        "Respuesta preparada\n"
    )


def test_cli_task_run_verbose_renders_coverage_details(monkeypatch, capsys) -> None:
    events = [
        {"type": "plan_ready", "data": {"units": ["u1", "u2", "u3"]}},
        {"type": "coverage_updated", "data": {"completed": ["u1"], "pending": ["u2"], "failed": ["u3"]}},
        {"type": "task_done", "data": {"response": "FINAL"}},
    ]
    monkeypatch.setattr(service, "stream_task", lambda **kwargs: iter(events))

    exit_code = main([
        "--config", "unused", "task", "run", "--prompt", "tarea", "--mode", "coverage", "--verbose",
    ])
    captured = capsys.readouterr()

    assert exit_code == 0
    assert captured.err == "Plan: 3 unidades\n  cobertura 1/3 (pendientes 1, fallidas 1)\n"


def test_cli_reasoning_stream_separates_output_and_steps(monkeypatch, capsys) -> None:
    events = [
        {"type": "step", "data": {"iteration": 1, "output": "draft"}},
        {"type": "step", "data": {"iteration": 2, "output": "final"}},
        {"type": "done", "data": {"output": "FINAL"}},
    ]
    monkeypatch.setattr(service, "stream_reasoning", lambda **kwargs: iter(events))

    exit_code = main([
        "--config", "unused", "reasoning", "stream", "--prompt", "tarea",
    ])
    captured = capsys.readouterr()

    assert exit_code == 0
    assert captured.out == "FINAL\n"
    assert "Paso 1" in captured.err
    assert "Paso 2" in captured.err
    assert "step" not in captured.out


def test_cli_reasoning_stream_verbose_includes_done(monkeypatch, capsys) -> None:
    events = [
        {"type": "step", "data": {"iteration": 1, "done": False, "output": "draft"}},
        {"type": "step", "data": {"iteration": 2, "done": True, "output": "final"}},
        {"type": "done", "data": {"output": "FINAL"}},
    ]
    monkeypatch.setattr(service, "stream_reasoning", lambda **kwargs: iter(events))

    exit_code = main([
        "--config", "unused", "reasoning", "stream", "--prompt", "tarea", "--verbose",
    ])
    captured = capsys.readouterr()

    assert exit_code == 0
    assert captured.out == "FINAL\n"
    assert captured.err == "Paso 1 (done=False)\nPaso 2 (done=True)\n"


def test_cli_reasoning_stream_quiet_suppresses_steps(monkeypatch, capsys) -> None:
    events = [
        {"type": "step", "data": {"iteration": 1, "output": "draft"}},
        {"type": "done", "data": {"output": "FINAL"}},
    ]
    monkeypatch.setattr(service, "stream_reasoning", lambda **kwargs: iter(events))

    exit_code = main([
        "--config", "unused", "reasoning", "stream", "--prompt", "tarea", "--quiet",
    ])
    captured = capsys.readouterr()

    assert exit_code == 0
    assert captured.out == "FINAL\n"
    assert captured.err == ""


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
    assert '"evaluation_attempts": 1' in body
    assert '"degradations": []' in body
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
    assert structured["requirements_covered"] is True
    assert structured["plan_attempts"] == 1
    assert structured["evaluation_attempts"] == 1
    assert structured["degradations"] == []
    assert calls[0]["mode"] == "coverage"

    async def call_task_default():
        return await server.call_tool("task.run", {"prompt": "tarea"})

    anyio.run(call_task_default)
    assert calls[1]["mode"] == "pipeline"
