from __future__ import annotations

import csv
import importlib.util
import json
from dataclasses import replace
from pathlib import Path

import pytest

from ianest_core.adapters import FakeAdapter
from ianest_core.cli import main
from ianest_core.config import load_config
from ianest_core.config.schema import TelemetryConfig
from ianest_core.errors import ConfigValidationError
from ianest_core.identity import Identity
from ianest_core.runtime import DomainRuntime, PromptRuntime, ReasoningRuntime
from ianest_core.telemetry import TRACE_CSV_FIELDS, TelemetryWriter
from ianest_core.telemetry.trace import SCHEMA_VERSION


ADR_0015_FIELDS = [
    "schema_version",
    "ts",
    "request_id",
    "event",
    "capability",
    "user_id",
    "service",
    "session_id",
    "domain_tag",
    "namespace",
    "domain",
    "model",
    "latency_ms",
    "tokens_in",
    "tokens_out",
    "verdict",
    "status",
    "error_type",
]


@pytest.mark.parametrize("profile", ["teen", "CHILD", 1])
def test_interlocutor_profile_rejects_values_outside_its_vocabulary(profile) -> None:
    with pytest.raises(ConfigValidationError) as exc:
        Identity.from_defaults({}, {"interlocutor_profile": profile})

    assert exc.value.type == "ConfigValidationError"
    assert exc.value.field == "interlocutor_profile"


@pytest.mark.parametrize("profile", ["adult", "child"])
def test_interlocutor_profile_is_in_trace_and_telemetry(profile, tmp_path) -> None:
    csv_path = tmp_path / "trace.csv"
    jsonl_path = tmp_path / "trace.jsonl"
    config = replace(
        load_config(Path("eval/fixtures/config.yaml")),
        telemetry=TelemetryConfig(csv_path=str(csv_path), jsonl_path=str(jsonl_path)),
    )
    identity = {"interlocutor_profile": profile}

    prompt = PromptRuntime(config)
    prompt_result = prompt.run(prompt="hola", domain_id="general", identity_override=identity)
    prompt_stream = list(prompt.stream(prompt="hola", domain_id="general", identity_override=identity))
    reasoning = ReasoningRuntime(config, adapter=FakeAdapter("fake_b", '{"output": "ok", "done": true}'))
    reasoning_result = reasoning.run(prompt="hola", domain_id="general", identity_override=identity)
    reasoning_stream = list(reasoning.stream(prompt="hola", domain_id="general", identity_override=identity))

    assert prompt_result.trace["interlocutor_profile"] == profile
    assert prompt_stream[-1].data["trace"]["interlocutor_profile"] == profile
    assert reasoning_result.trace["interlocutor_profile"] == profile
    assert reasoning_stream[-1].data["trace"]["interlocutor_profile"] == profile

    with csv_path.open(newline="", encoding="utf-8") as handle:
        rows = list(csv.DictReader(handle, delimiter=";"))
    assert list(rows[0]) == TRACE_CSV_FIELDS
    assert TRACE_CSV_FIELDS[:-1] == ADR_0015_FIELDS
    assert TRACE_CSV_FIELDS[-1] == "interlocutor_profile"
    assert {row["schema_version"] for row in rows} == {"2"}
    assert {row["interlocutor_profile"] for row in rows} == {profile}
    events = [json.loads(line) for line in jsonl_path.read_text(encoding="utf-8").splitlines()]
    assert {event["schema_version"] for event in events} == {"2"}
    assert {event["interlocutor_profile"] for event in events} == {profile}


def test_telemetry_rotates_csv_with_old_header_before_appending(tmp_path) -> None:
    csv_path = tmp_path / "trace.csv"
    with csv_path.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.writer(handle, delimiter=";")
        writer.writerow(ADR_0015_FIELDS)
        writer.writerow(["1"] + [""] * (len(ADR_0015_FIELDS) - 1))
    old_content = csv_path.read_text(encoding="utf-8")
    writer = TelemetryWriter(TelemetryConfig(csv_path=str(csv_path), jsonl_path=""))

    writer.record(
        request_id="new-schema",
        event="done",
        capability="prompt.run",
        identity=Identity(interlocutor_profile="child"),
    )

    rotated = list(tmp_path.glob("trace.csv.*"))
    assert len(rotated) == 1
    assert rotated[0].read_text(encoding="utf-8") == old_content
    with csv_path.open(newline="", encoding="utf-8") as handle:
        rows = list(csv.reader(handle, delimiter=";"))
    assert rows[0] == TRACE_CSV_FIELDS
    assert len(rows[1]) == len(TRACE_CSV_FIELDS)
    assert rows[1][0] == SCHEMA_VERSION
    assert rows[1][-1] == "child"


def test_telemetry_appends_to_csv_with_current_header_without_rotation(tmp_path) -> None:
    csv_path = tmp_path / "trace.csv"
    with csv_path.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.writer(handle, delimiter=";")
        writer.writerow(TRACE_CSV_FIELDS)
        writer.writerow([SCHEMA_VERSION] + [""] * (len(TRACE_CSV_FIELDS) - 1))
    writer = TelemetryWriter(TelemetryConfig(csv_path=str(csv_path), jsonl_path=""))

    writer.record(
        request_id="same-schema",
        event="done",
        capability="prompt.run",
        identity=Identity(interlocutor_profile="adult"),
    )

    assert not list(tmp_path.glob("trace.csv.*"))
    with csv_path.open(newline="", encoding="utf-8") as handle:
        rows = list(csv.reader(handle, delimiter=";"))
    assert rows[0] == TRACE_CSV_FIELDS
    assert len(rows) == 3
    assert rows[-1][-1] == "adult"


def test_interlocutor_profile_absent_is_empty_in_trace() -> None:
    config = load_config(Path("eval/fixtures/config.yaml"))

    result = PromptRuntime(config).run(prompt="hola", domain_id="general")

    assert result.trace["interlocutor_profile"] == ""


@pytest.mark.parametrize("profile", ["adult", "child"])
def test_domain_route_traces_interlocutor_profile(profile, tmp_path) -> None:
    jsonl_path = tmp_path / "trace.jsonl"
    config = replace(
        load_config(Path("eval/fixtures/router.yaml")),
        telemetry=TelemetryConfig(csv_path=str(tmp_path / "trace.csv"), jsonl_path=str(jsonl_path)),
    )

    result = DomainRuntime(config).route(
        prompt="hola",
        identity_override={"interlocutor_profile": profile},
    )

    assert result.trace["interlocutor_profile"] == profile
    events = [json.loads(line) for line in jsonl_path.read_text(encoding="utf-8").splitlines()]
    assert {event["interlocutor_profile"] for event in events} == {profile}


def test_invalid_interlocutor_profile_does_not_reach_the_model() -> None:
    config = load_config(Path("eval/fixtures/config.yaml"))

    class FailingAdapter:
        def stream(self, req):
            raise AssertionError("the model must not be called")

    with pytest.raises(ConfigValidationError):
        PromptRuntime(config, adapter_factory=lambda model: FailingAdapter()).run(
            prompt="hola",
            domain_id="general",
            identity_override={"interlocutor_profile": "teen"},
        )


def test_interlocutor_profile_does_not_change_model_messages_or_resolution() -> None:
    config = load_config(Path("eval/fixtures/config.yaml"))
    adapters = []

    class RecordingAdapter(FakeAdapter):
        def __init__(self) -> None:
            super().__init__("fake_b", "respuesta")
            self.messages = []

        def stream(self, req):
            self.messages.append(req.messages)
            yield from super().stream(req)

    for profile in ("child", "adult"):
        adapter = RecordingAdapter()
        result = PromptRuntime(config, adapter_factory=lambda model: adapter).run(
            prompt="hola",
            domain_id="general",
            identity_override={"interlocutor_profile": profile},
        )
        adapters.append((result, adapter.messages))

    child, adult = adapters
    assert (child[0].model, child[0].domain, child[0].params) == (
        adult[0].model,
        adult[0].domain,
        adult[0].params,
    )
    assert child[1] == adult[1]


def test_cli_forwards_interlocutor_profile(monkeypatch, capsys) -> None:
    from ianest_core import service

    calls = []
    monkeypatch.setattr(service, "run_prompt", lambda **kwargs: calls.append(kwargs) or {"response": "ok"})

    assert main([
        "--config", "unused", "prompt", "run", "--prompt", "hola", "--interlocutor-profile", "child", "--json",
    ]) == 0

    assert calls[0]["identity"] == {"interlocutor_profile": "child"}
    assert json.loads(capsys.readouterr().out) == {"response": "ok"}


@pytest.mark.skipif(
    importlib.util.find_spec("starlette") is None or importlib.util.find_spec("httpx") is None,
    reason="REST extras not installed",
)
def test_rest_rejects_invalid_interlocutor_profile_with_400() -> None:
    import anyio
    import httpx
    from ianest_core.rest import create_app

    async def request():
        transport = httpx.ASGITransport(app=create_app("eval/fixtures/config.yaml"))
        async with httpx.AsyncClient(transport=transport, base_url="http://test") as client:
            return await client.post(
                "/prompt/run",
                json={"prompt": "hola", "domain": "general", "identity": {"interlocutor_profile": "teen"}},
            )

    response = anyio.run(request)

    assert response.status_code == 400
    assert response.json()["error"]["type"] == "ConfigValidationError"
    assert response.json()["error"]["field"] == "interlocutor_profile"


@pytest.mark.skipif(importlib.util.find_spec("mcp") is None, reason="MCP extra not installed")
def test_mcp_accepts_interlocutor_profile(monkeypatch) -> None:
    import anyio
    from ianest_core import service
    from ianest_core.mcp_server import create_server

    calls = []
    monkeypatch.setattr(service, "run_prompt", lambda **kwargs: calls.append(kwargs) or {"ok": True})

    async def call_tool():
        return await create_server("unused").call_tool(
            "prompt.run",
            {"prompt": "hola", "identity": {"interlocutor_profile": "child"}},
        )

    _, result = anyio.run(call_tool)

    assert result == {"ok": True}
    assert calls[0]["identity"]["interlocutor_profile"] == "child"


@pytest.mark.skipif(importlib.util.find_spec("mcp") is None, reason="MCP extra not installed")
def test_mcp_rejects_invalid_interlocutor_profile() -> None:
    import anyio
    from mcp.server.fastmcp.exceptions import ToolError
    from ianest_core.mcp_server import create_server

    async def call_tool():
        return await create_server("eval/fixtures/config.yaml").call_tool(
            "prompt.run",
            {"prompt": "hola", "domain": "general", "identity": {"interlocutor_profile": "teen"}},
        )

    with pytest.raises(ToolError, match="interlocutor_profile must be adult or child"):
        anyio.run(call_tool)
