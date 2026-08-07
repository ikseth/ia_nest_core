from __future__ import annotations

import csv
import json
from dataclasses import replace
from pathlib import Path

from ianest_core.adapters import (
    FakeAdapter,
    ModelRequest,
    OpenAICompatibleAdapter,
    ScriptedFakeAdapter,
    run_blocking,
    split_reasoning,
)
from ianest_core.adapters import openai_compatible
from ianest_core.adapters.base import Event
from ianest_core.config import load_config
from ianest_core.config.schema import TelemetryConfig
from ianest_core.identity import Identity
from ianest_core.runtime import PromptRuntime
from ianest_core.telemetry import TRACE_CSV_FIELDS, TelemetryWriter


def test_run_blocking_collects_fake_d2_flow() -> None:
    adapter = FakeAdapter(model="fake_a", response_text="hola mundo")
    req = ModelRequest(messages=[{"role": "user", "content": "hola"}])

    response = run_blocking(adapter, req)

    assert response.text == "hola mundo"
    assert response.model == "fake_a"
    assert response.tokens_in == 1
    assert response.tokens_out == 2
    assert response.finish_reason == "stop"
    assert response.reasoning == ""


def test_split_reasoning_removes_simple_block() -> None:
    assert split_reasoning("<think>analisis</think>respuesta") == ("respuesta", "analisis")


def test_split_reasoning_supports_multiline_block() -> None:
    text = "antes<think>linea uno\nlinea dos</think>despues"

    assert split_reasoning(text) == ("antesdespues", "linea uno\nlinea dos")


def test_split_reasoning_supports_multiple_blocks() -> None:
    text = "<think>uno</think>A<think>dos</think>B"

    assert split_reasoning(text) == ("AB", "uno\ndos")


def test_split_reasoning_leaves_unmarked_text_intact() -> None:
    text = "  respuesta sin marcas\n"

    assert split_reasoning(text) == (text, "")


def test_split_reasoning_tolerates_spaces_in_tags() -> None:
    assert split_reasoning("< think >interno< / think >visible") == ("visible", "interno")


def test_run_blocking_separates_inline_and_adapter_reasoning() -> None:
    req = ModelRequest(messages=[{"role": "user", "content": "hola"}])

    response = run_blocking(ReasoningAdapter(), req)

    assert response.text == "respuesta"
    assert response.reasoning == "del cable\ndel bloque"


def test_run_blocking_cleans_inline_reasoning_from_fake_adapter() -> None:
    adapter = FakeAdapter(model="fake_b", response_text="<think>interno</think>respuesta")
    req = ModelRequest(messages=[{"role": "user", "content": "hola"}])

    response = run_blocking(adapter, req)

    assert response.text == "respuesta"
    assert response.reasoning == "interno"


def test_openai_compatible_surfaces_last_non_null_finish_reason(monkeypatch) -> None:
    lines = [
        b'data: {"choices":[{"delta":{"content":"hola"},"finish_reason":null}]}\n',
        b'data: {"choices":[{"delta":{},"finish_reason":"length"}]}\n',
        b'data: {"choices":[],"usage":{"prompt_tokens":1,"completion_tokens":1}}\n',
        b'data: [DONE]\n',
    ]
    monkeypatch.setattr(openai_compatible, "urlopen", lambda request, timeout: _StreamResponse(lines))

    events = list(
        OpenAICompatibleAdapter("http://backend.test", "model-a").stream(
            ModelRequest(messages=[{"role": "user", "content": "hola"}])
        )
    )

    assert events[-1].type == "done"
    assert events[-1].data["finish_reason"] == "length"


def test_openai_compatible_captures_reasoning_separately(monkeypatch) -> None:
    lines = [
        b'data: {"choices":[{"delta":{"reasoning_content":"pienso "},"finish_reason":null}]}\n',
        b'data: {"choices":[{"delta":{"reasoning":"ignorado"},"finish_reason":null}]}\n',
        b'data: {"choices":[{"delta":{"content":"respuesta"},"finish_reason":"stop"}]}\n',
        b'data: [DONE]\n',
    ]
    monkeypatch.setattr(openai_compatible, "urlopen", lambda request, timeout: _StreamResponse(lines))

    events = list(
        OpenAICompatibleAdapter("http://backend.test", "model-a").stream(
            ModelRequest(messages=[{"role": "user", "content": "hola"}])
        )
    )

    assert [event.data["text"] for event in events if event.type == "token"] == ["respuesta"]
    assert events[-1].data["text"] == "respuesta"
    assert events[-1].data["reasoning"] == "pienso ignorado"


def test_prompt_runtime_records_reasoning_only_in_jsonl(tmp_path) -> None:
    csv_path = tmp_path / "trace.csv"
    jsonl_path = tmp_path / "trace.jsonl"
    config = replace(
        load_config(Path("eval/fixtures/config.yaml")),
        telemetry=TelemetryConfig(
            csv_path=str(csv_path),
            jsonl_path=str(jsonl_path),
            strict_mode=False,
        ),
    )
    adapter = FakeAdapter(model="fake_b", response_text="<think>del bloque</think>respuesta")
    runtime = PromptRuntime(config, adapter_factory=lambda model: adapter)

    result = runtime.run(prompt="hola", domain_id="general", request_id="reasoning-clean")

    assert result.response == "respuesta"
    events = [json.loads(line) for line in jsonl_path.read_text(encoding="utf-8").splitlines()]
    done = next(event for event in events if event["event"] == "done")
    assert done["payload"]["response"] == "respuesta"
    assert done["payload"]["reasoning"] == "del bloque"
    assert "del bloque" not in csv_path.read_text(encoding="utf-8")


def test_prompt_runtime_stream_records_clean_response_and_reasoning(tmp_path) -> None:
    jsonl_path = tmp_path / "trace.jsonl"
    config = replace(
        load_config(Path("eval/fixtures/config.yaml")),
        telemetry=TelemetryConfig(
            csv_path=str(tmp_path / "trace.csv"),
            jsonl_path=str(jsonl_path),
            strict_mode=False,
        ),
    )
    runtime = PromptRuntime(config, adapter_factory=lambda model: ReasoningAdapter())

    streamed = list(runtime.stream(prompt="hola", domain_id="general", request_id="reasoning-stream"))

    assert "<think>del bloque</think>" in "".join(
        event.data.get("text", "") for event in streamed if event.type == "token"
    )
    events = [json.loads(line) for line in jsonl_path.read_text(encoding="utf-8").splitlines()]
    done = next(event for event in events if event["event"] == "done")
    assert done["payload"]["response"] == "respuesta"
    assert done["payload"]["reasoning"] == "del cable\ndel bloque"


def test_scripted_finish_reason_reaches_prompt_trace_and_jsonl(tmp_path) -> None:
    config = replace(
        load_config(Path("eval/fixtures/config.yaml")),
        telemetry=TelemetryConfig(
            csv_path=str(tmp_path / "trace.csv"),
            jsonl_path=str(tmp_path / "trace.jsonl"),
            strict_mode=False,
        ),
    )
    adapter = ScriptedFakeAdapter("fake_b", ["respuesta"], finish_reason="length")
    runtime = PromptRuntime(config, adapter_factory=lambda model: adapter)

    result = runtime.run(prompt="hola", domain_id="general", request_id="finish-reason")

    assert result.trace["finish_reason"] == "length"
    events = [json.loads(line) for line in (tmp_path / "trace.jsonl").read_text().splitlines()]
    done = next(event for event in events if event["event"] == "done")
    assert done["payload"]["finish_reason"] == "length"

    with (tmp_path / "trace.csv").open("r", newline="", encoding="utf-8") as handle:
        rows = list(csv.reader(handle, delimiter=";"))
    assert rows
    assert all(len(row) == 18 for row in rows)


def test_prompt_runtime_propagates_identity_to_trace(tmp_path) -> None:
    csv_path = tmp_path / "stream_trace.csv"
    jsonl_path = tmp_path / "stream_trace.jsonl"
    config = replace(
        load_config(Path("eval/fixtures/config.yaml")),
        telemetry=TelemetryConfig(csv_path=str(csv_path), jsonl_path=str(jsonl_path), strict_mode=False),
    )
    runtime = PromptRuntime(config)

    result = runtime.run(
        prompt="hola",
        domain_id="general",
        identity_override={"user_id": "u42", "service": "local_cli", "session_id": "s1"},
        request_id="req-test",
    )

    assert result.model == "fake_b"
    assert result.domain == "general"
    assert result.trace["request_id"] == "req-test"
    assert result.trace["user_id"] == "u42"
    assert result.trace["service"] == "local_cli"
    assert result.trace["session_id"] == "s1"
    assert result.trace["domain_tag"] == "general"
    assert result.trace["tokens_out"] > 0

    with csv_path.open("r", newline="", encoding="utf-8") as handle:
        rows = list(csv.DictReader(handle, delimiter=";"))

    assert rows
    assert list(rows[0].keys()) == TRACE_CSV_FIELDS
    done = [row for row in rows if row["event"] == "done"][0]
    assert done["user_id"] == "u42"
    assert done["service"] == "local_cli"
    assert done["session_id"] == "s1"
    assert done["domain_tag"] == "general"
    assert done["model"] == "fake_b"
    assert done["status"] == "ok"

    events = [json.loads(line) for line in jsonl_path.read_text(encoding="utf-8").splitlines()]
    done_json = [event for event in events if event["event"] == "done"][0]
    assert done_json["payload"]["response"] == result.response
    assert done_json["payload"]["finish_reason"] == "stop"
    assert done_json["user_id"] == "u42"


def test_telemetry_non_serializable_payload_is_best_effort(tmp_path) -> None:
    writer = TelemetryWriter(
        TelemetryConfig(
            csv_path=str(tmp_path / "trace.csv"),
            jsonl_path=str(tmp_path / "trace.jsonl"),
            strict_mode=False,
        )
    )

    writer.record(
        request_id="req",
        event="done",
        capability="prompt.run",
        identity=Identity(user_id="u1", service="local_cli"),
        payload={"bad": object()},
    )

    assert writer.errors

    csv_path = tmp_path / "stream_trace.csv"
    jsonl_path = tmp_path / "stream_trace.jsonl"
    config = replace(
        load_config(Path("eval/fixtures/config.yaml")),
        telemetry=TelemetryConfig(csv_path=str(csv_path), jsonl_path=str(jsonl_path), strict_mode=False),
    )
    runtime = PromptRuntime(config)
    runtime._adapter_for = lambda model: ErrorAdapter()  # type: ignore[method-assign]

    events = list(runtime.stream(prompt="hola", domain_id="general", request_id="stream-error"))

    assert events[-1].type == "error"
    csv_text = csv_path.read_text(encoding="utf-8")
    assert ";error;" in csv_text
    assert ";done;" not in csv_text


class ErrorAdapter:
    def stream(self, req: ModelRequest):
        yield Event("error", {"type": "AdapterError", "message": "boom"})


class ReasoningAdapter:
    def stream(self, req: ModelRequest):
        text = "<think>del bloque</think>respuesta"
        yield Event("token", {"text": text})
        yield Event(
            "done",
            {
                "text": text,
                "model": "fake_b",
                "tokens_in": 1,
                "tokens_out": 2,
                "finish_reason": "stop",
                "reasoning": "del cable",
            },
        )


class _StreamResponse:
    def __init__(self, lines: list[bytes]) -> None:
        self.lines = lines

    def __enter__(self):
        return iter(self.lines)

    def __exit__(self, exc_type, exc, traceback) -> None:
        return None
