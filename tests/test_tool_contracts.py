from __future__ import annotations

import builtins
import gc
import importlib.util
import json
import socket
import subprocess
import sys
import time
from contextlib import contextmanager
from pathlib import Path
from typing import Any

import pytest

from ianest_core.adapters import ModelRequest, OpenAICompatibleAdapter, ScriptedFakeAdapter
from ianest_core.adapters import openai_compatible
from ianest_core.config import load_config_data, load_config_from_dict, validate_config_dict
from ianest_core.config.schema import TelemetryConfig, ToolProviderConfig
from ianest_core.errors import ConfigValidationError
from ianest_core.mcp_client import MCPClientTurn, ToolCallResult
from ianest_core.runtime import PromptRuntime
from ianest_core.tool_contracts import ProviderTool, invocation_is_allowed, offered_tools


HAS_MCP = importlib.util.find_spec("mcp") is not None


def test_config_without_tool_sections_loads_unchanged() -> None:
    raw = load_config_data("eval/fixtures/config.yaml")

    validate_config_dict(raw)
    config = load_config_from_dict(raw)

    assert config.tool_providers == {}
    assert all(domain.tools is None for domain in config.domains)


def test_tool_config_loads_defaults() -> None:
    raw = _tool_config_raw()
    raw["tool_providers"]["house"].pop("timeout_s")
    raw["domains"][0]["tools"].pop("max_rounds")

    validate_config_dict(raw)
    config = load_config_from_dict(raw)

    assert config.tool_providers["house"].timeout_s == 10
    assert config.domains[0].tools is not None
    assert config.domains[0].tools.max_rounds == 4


@pytest.mark.parametrize(
    ("mutate", "field"),
    [
        (lambda raw: raw.update(tool_providers=[]), "tool_providers"),
        (
            lambda raw: raw["tool_providers"]["house"].update(transport="sse"),
            "tool_providers.house.transport",
        ),
        (lambda raw: raw["tool_providers"]["house"].update(url=""), "tool_providers.house.url"),
        (
            lambda raw: raw["tool_providers"]["house"].update(auth_env="bad-name"),
            "tool_providers.house.auth_env",
        ),
        (
            lambda raw: raw["tool_providers"]["house"].update(timeout_s=0),
            "tool_providers.house.timeout_s",
        ),
        (lambda raw: raw["domains"][0]["tools"].update(provider="missing"), "tools.provider"),
        (lambda raw: raw["domains"][0]["tools"].update(max_rounds=0), "tools.max_rounds"),
        (
            lambda raw: raw["domains"][0]["tools"]["allow"].update(teen=["get_state"]),
            "tools.allow.teen",
        ),
        (lambda raw: raw["domains"][0]["tools"].update(allow=[]), "tools.allow"),
        (lambda raw: raw["domains"][0]["tools"].update(deny="mystery"), "tools.deny"),
    ],
)
def test_tool_config_validation_rules(mutate, field: str) -> None:
    raw = _tool_config_raw()
    mutate(raw)

    with pytest.raises(ConfigValidationError) as exc:
        validate_config_dict(raw)

    assert exc.value.field == field


def test_policy_denies_empty_profile_deny_and_destructive_tools() -> None:
    domain = load_config_from_dict(_tool_config_raw()).domains[0]
    tools = [
        _provider_tool("get_state", {"readOnlyHint": True}),
        _provider_tool("light_on", {"destructiveHint": False}),
        _provider_tool("light_off", {"destructiveHint": False}),
        _provider_tool("lock_open", {"destructiveHint": True}),
        _provider_tool("mystery", None),
    ]

    assert offered_tools(domain, "", tools) == []
    assert [tool.name for tool in offered_tools(domain, "child", tools)] == ["get_state", "light_on"]
    assert "light_off" not in [tool.name for tool in offered_tools(domain, "adult", tools)]
    assert not invocation_is_allowed(domain, "adult", tools, "house", "lock_open")
    assert not invocation_is_allowed(domain, "adult", tools, "house", "mystery")


def test_policy_requires_declared_provider() -> None:
    domain = load_config_from_dict(_tool_config_raw()).domains[0]

    assert offered_tools(
        domain,
        "child",
        [ProviderTool("other", "get_state", annotations={"readOnlyHint": True})],
    ) == []


def test_openai_body_is_unchanged_without_tools_and_maps_mcp_schema(monkeypatch) -> None:
    bodies: list[bytes] = []

    def fake_urlopen(request, timeout):
        bodies.append(request.data)
        return _StreamResponse([b'data: {"choices":[{"delta":{},"finish_reason":"stop"}]}\n'])

    monkeypatch.setattr(openai_compatible, "urlopen", fake_urlopen)
    adapter = OpenAICompatibleAdapter("http://backend.test", "model-a")
    base = ModelRequest(messages=[{"role": "user", "content": "hola"}], params={"temperature": 0.2})
    list(adapter.stream(base))
    list(
        adapter.stream(
            ModelRequest(
                messages=base.messages,
                params=base.params,
                tools=[
                    {
                        "type": "function",
                        "function": {
                            "name": "get_state",
                            "description": "Read state",
                            "parameters": {"type": "object", "properties": {}},
                        },
                    }
                ],
            )
        )
    )

    expected = json.dumps(
        {
            "model": "model-a",
            "messages": [{"role": "user", "content": "hola"}],
            "stream": True,
            "stream_options": {"include_usage": True},
            "temperature": 0.2,
        }
    ).encode("utf-8")
    assert bodies[0] == expected
    assert "tools" not in json.loads(bodies[0])
    assert json.loads(bodies[1])["tools"][0]["function"]["parameters"] == {
        "type": "object",
        "properties": {},
    }


def test_openai_accumulates_fragmented_tool_calls(monkeypatch) -> None:
    lines = [
        b'data: {"choices":[{"delta":{"tool_calls":[{"index":0,"id":"call_","function":{"name":"light_","arguments":"{\\"na"}}]},"finish_reason":null}]}\n',
        b'data: {"choices":[{"delta":{"tool_calls":[{"index":0,"function":{"name":"on","arguments":"me\\":\\"desk\\"}"}}]},"finish_reason":"tool_calls"}]}\n',
    ]
    monkeypatch.setattr(openai_compatible, "urlopen", lambda request, timeout: _StreamResponse(lines))

    events = list(
        OpenAICompatibleAdapter("http://backend.test", "model-a").stream(
            ModelRequest(messages=[{"role": "user", "content": "on"}], tools=[])
        )
    )

    assert events[-1].data["tool_calls"] == [
        {
            "id": "call_",
            "type": "function",
            "function": {"name": "light_on", "arguments": '{"name":"desk"}'},
        }
    ]


@pytest.mark.parametrize("with_index", [True, False])
def test_openai_keeps_complete_tool_calls_in_separate_chunks(monkeypatch, with_index: bool) -> None:
    def chunk(call: dict[str, Any], finish_reason: str | None) -> bytes:
        return (
            "data: "
            + json.dumps(
                {"choices": [{"delta": {"tool_calls": [call]}, "finish_reason": finish_reason}]}
            )
            + "\n"
        ).encode()

    first = {
        "id": "call_first",
        "function": {"name": "get_state", "arguments": "{}"},
    }
    second = {
        "id": "call_second",
        "function": {"name": "light_on", "arguments": '{"name":"desk"}'},
    }
    if with_index:
        first["index"] = 0
        second["index"] = 0
    lines = [
        chunk(first, None),
        chunk(second, "tool_calls"),
    ]
    monkeypatch.setattr(openai_compatible, "urlopen", lambda request, timeout: _StreamResponse(lines))

    events = list(
        OpenAICompatibleAdapter("http://backend.test", "model-a").stream(
            ModelRequest(messages=[{"role": "user", "content": "on"}], tools=[])
        )
    )

    assert events[-1].data["tool_calls"] == [
        {
            "id": "call_first",
            "type": "function",
            "function": {"name": "get_state", "arguments": "{}"},
        },
        {
            "id": "call_second",
            "type": "function",
            "function": {"name": "light_on", "arguments": '{"name":"desk"}'},
        },
    ]
def test_domain_without_tools_has_zero_calls_and_no_tools_offered(tmp_path) -> None:
    raw = load_config_data("eval/fixtures/config.yaml")
    raw["telemetry"] = _telemetry_raw(tmp_path)
    adapter = ScriptedFakeAdapter("fake_b", ["same response"])
    runtime = PromptRuntime(load_config_from_dict(raw), adapter_factory=lambda model: adapter)

    result = runtime.run(prompt="hola", domain_id="general", request_id="no-tools")

    assert result.response == "same response"
    assert result.trace["tool_calls"] == 0
    assert adapter.requests[0].tools is None
    events = _jsonl_events(tmp_path)
    assert all(event["event"] != "tools_offered" for event in events)


def test_internal_task_prompt_does_not_enable_domain_tools(tmp_path) -> None:
    adapter = ScriptedFakeAdapter("fake_a", ["unused"])
    runtime = _tool_runtime(tmp_path, adapter, FakeTurn(_all_provider_tools()))

    prepared = runtime._prepare(
        prompt="subtask",
        model_id=None,
        domain_id="support",
        identity_override={"interlocutor_profile": "adult"},
        request_id="task-child",
        trace_payload={"task_id": "task", "parent_request_id": "parent"},
    )

    assert not runtime._uses_tools(prepared)


def test_child_only_sees_child_tools_and_forced_adult_call_is_denied(tmp_path) -> None:
    adapter = ScriptedFakeAdapter(
        "fake_b",
        [_tool_response("climate_set", '{"name":"hall","temperature":22}'), "not allowed"],
    )
    turn = FakeTurn(_all_provider_tools())
    runtime = _tool_runtime(tmp_path, adapter, turn)

    result = runtime.run(
        prompt="set climate",
        domain_id="support",
        identity_override={"interlocutor_profile": "child"},
        request_id="child-denied",
    )

    assert result.response == "not allowed"
    assert result.trace["tool_calls"] == 1
    assert turn.calls == []
    events = _jsonl_events(tmp_path)
    offered = next(event for event in events if event["event"] == "tools_offered")
    assert offered["payload"]["tools"] == ["get_state", "light_on"]
    call = next(event for event in events if event["event"] == "tool_call")
    assert call["payload"]["status"] == "denied"


def test_provider_down_adds_system_note_and_turn_continues(tmp_path) -> None:
    adapter = ScriptedFakeAdapter("fake_b", ["Tools are unavailable; I cannot know the state."])
    runtime = _tool_runtime(tmp_path, adapter, UnavailableTurn())

    result = runtime.run(
        prompt="is the light on",
        domain_id="support",
        identity_override={"interlocutor_profile": "adult"},
    )

    assert "unavailable" in result.response
    assert adapter.requests[0].tools is None
    system_text = " ".join(
        str(message["content"])
        for message in adapter.requests[0].messages
        if message["role"] == "system"
    )
    assert "do not assume or invent any state" in system_text
    assert next(
        event for event in _jsonl_events(tmp_path) if event["event"] == "tools_offered"
    )["payload"]["tools"] == []


def test_max_rounds_records_limit_and_final_call_has_no_tools(tmp_path) -> None:
    adapter = ScriptedFakeAdapter(
        "fake_b",
        [_tool_response("get_state", "{}"), _tool_response("get_state", "{}"), "final answer"],
    )
    turn = FakeTurn(_all_provider_tools())
    runtime = _tool_runtime(tmp_path, adapter, turn, max_rounds=2)

    result = runtime.run(
        prompt="loop",
        domain_id="support",
        identity_override={"interlocutor_profile": "adult"},
    )

    assert result.response == "final answer"
    assert result.trace["tool_calls"] == 2
    assert [request.tools is None for request in adapter.requests] == [False, False, True]
    statuses = [
        event["payload"]["status"]
        for event in _jsonl_events(tmp_path)
        if event["event"] == "tool_call"
    ]
    assert statuses == ["invoked", "limit"]


def test_multiple_calls_are_invoked_in_model_order(tmp_path) -> None:
    first_round = {
        "text": "",
        "finish_reason": "tool_calls",
        "tool_calls": [
            _tool_response("get_state", "{}")["tool_calls"][0],
            _tool_response("light_on", '{"name":"desk"}')["tool_calls"][0],
        ],
    }
    adapter = ScriptedFakeAdapter("fake_b", [first_round, "done"])
    turn = FakeTurn(_all_provider_tools())
    runtime = _tool_runtime(tmp_path, adapter, turn)

    runtime.run(
        prompt="read then act",
        domain_id="support",
        identity_override={"interlocutor_profile": "adult"},
    )

    assert turn.calls == [("get_state", {}), ("light_on", {"name": "desk"})]
    tool_messages = [
        message for message in adapter.requests[1].messages if message["role"] == "tool"
    ]
    assert [message["tool_call_id"] for message in tool_messages] == [
        "call_get_state",
        "call_light_on",
    ]


def test_mcp_is_error_returns_short_tool_result_and_turn_continues(tmp_path) -> None:
    adapter = ScriptedFakeAdapter("fake_b", [_tool_response("get_state", "{}"), "fallback"])
    turn = FakeTurn(_all_provider_tools(), result="provider exploded", is_error=True)
    runtime = _tool_runtime(tmp_path, adapter, turn)

    result = runtime.run(
        prompt="state",
        domain_id="support",
        identity_override={"interlocutor_profile": "adult"},
    )

    assert result.response == "fallback"
    tool_message = next(
        message for message in adapter.requests[1].messages if message["role"] == "tool"
    )
    assert tool_message["content"] == "error: get_state failed: provider exploded"
    call = next(event for event in _jsonl_events(tmp_path) if event["event"] == "tool_call")
    assert call["payload"]["status"] == "error"


def test_stream_emits_all_round_tokens_one_done_and_no_new_event_type(tmp_path) -> None:
    adapter = ScriptedFakeAdapter(
        "fake_b",
        [{**_tool_response("get_state", "{}"), "text": "checking"}, "finished"],
    )
    runtime = _tool_runtime(tmp_path, adapter, FakeTurn(_all_provider_tools()))

    events = list(
        runtime.stream(
            prompt="state",
            domain_id="support",
            identity_override={"interlocutor_profile": "adult"},
        )
    )

    assert {event.type for event in events} == {"token", "done"}
    assert [event.data["text"] for event in events if event.type == "token"] == [
        "checking",
        "finished",
    ]
    done = [event for event in events if event.type == "done"]
    assert len(done) == 1
    assert done[0].data["text"] == "finished"
    assert done[0].data["trace"]["tool_calls"] == 1


@pytest.mark.parametrize("stream", [False, True])
def test_tool_session_close_failure_keeps_completed_response_and_closes_in_turn(
    tmp_path, monkeypatch, caplog, stream: bool
) -> None:
    adapter = ScriptedFakeAdapter("fake_b", ["completed response"])
    turn = ClosingFailureTurn(_all_provider_tools())
    runtime = _tool_runtime(tmp_path, adapter, turn)
    unraisable: list[Any] = []
    monkeypatch.setattr(sys, "unraisablehook", lambda item: unraisable.append(item))

    if stream:
        events = list(
            runtime.stream(
                prompt="state",
                domain_id="support",
                identity_override={"interlocutor_profile": "adult"},
            )
        )
        done = [event for event in events if event.type == "done"]
        assert len(done) == 1
        assert done[0].data["text"] == "completed response"
    else:
        result = runtime.run(
            prompt="state",
            domain_id="support",
            identity_override={"interlocutor_profile": "adult"},
        )
        assert result.response == "completed response"

    gc.collect()
    assert turn.exit_calls == 1
    assert unraisable == []
    assert "MCP tool session close failed" in caplog.text


def test_tool_result_preview_is_utf8_safe_and_sized_in_bytes(tmp_path) -> None:
    long_result = "a" * 2047 + "n" + "\u00f1" + "tail"
    adapter = ScriptedFakeAdapter("fake_b", [_tool_response("get_state", "{}"), "done"])
    turn = FakeTurn(_all_provider_tools(), result=long_result)
    runtime = _tool_runtime(tmp_path, adapter, turn)

    runtime.run(
        prompt="state",
        domain_id="support",
        identity_override={"interlocutor_profile": "adult"},
    )

    payload = next(
        event["payload"]
        for event in _jsonl_events(tmp_path)
        if event["event"] == "tool_call"
    )
    assert payload["result_size_bytes"] == len(long_result.encode("utf-8"))
    assert len(payload["result"].encode("utf-8")) <= 2048
    payload["result"].encode("utf-8").decode("utf-8")


def test_missing_mcp_extra_is_clear_config_error(monkeypatch) -> None:
    original_import = builtins.__import__

    def without_mcp(name, *args, **kwargs):
        if name == "mcp" or name.startswith("mcp."):
            raise ImportError("no mcp")
        return original_import(name, *args, **kwargs)

    monkeypatch.setattr(builtins, "__import__", without_mcp)
    provider = ToolProviderConfig("house", "streamable_http", "http://localhost:1/mcp")

    with pytest.raises(ConfigValidationError, match=r"install ianest-core\[interfaces\]"):
        with MCPClientTurn(provider):
            pass


@pytest.mark.skipif(not HAS_MCP, reason="MCP extra not installed")
def test_real_provider_invocation_from_active_event_loop(tmp_path, monkeypatch) -> None:
    import anyio

    with _running_provider(token="test-token") as (url, token):
        monkeypatch.setenv("IANEST_TEST_PROVIDER_TOKEN", token)
        raw = _tool_config_raw(url=url, auth_env="IANEST_TEST_PROVIDER_TOKEN")
        raw["telemetry"] = _telemetry_raw(tmp_path)
        adapter = ScriptedFakeAdapter(
            "fake_b",
            [_tool_response("light_on", '{"name":"desk"}'), "The desk light is on."],
        )
        runtime = PromptRuntime(load_config_from_dict(raw), adapter_factory=lambda model: adapter)

        async def invoke_inside_loop():
            result = runtime.run(
                prompt="turn on desk",
                domain_id="support",
                identity_override={"interlocutor_profile": "adult"},
            )
            provider = runtime.config.tool_providers["house"]
            with MCPClientTurn(provider) as client:
                state = client.call_tool("get_state", {})
            return result, state

        result, state = anyio.run(invoke_inside_loop)

    assert result.response == "The desk light is on."
    assert result.trace["tool_calls"] == 1
    assert json.loads(state.text)["lights"]["desk"] is True
    call = next(event for event in _jsonl_events(tmp_path) if event["event"] == "tool_call")
    assert call["payload"]["status"] == "invoked"
    assert call["payload"]["arguments"] == {"name": "desk"}


class FakeTurn:
    def __init__(
        self,
        tools: list[ProviderTool],
        result: str = '{"ok": true}',
        is_error: bool = False,
    ) -> None:
        self.tools = tools
        self.result = result
        self.is_error = is_error
        self.calls: list[tuple[str, dict[str, Any]]] = []

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc, traceback) -> None:
        return None

    def list_tools(self) -> list[ProviderTool]:
        return self.tools

    def call_tool(self, name: str, arguments: dict[str, Any]) -> ToolCallResult:
        self.calls.append((name, arguments))
        return ToolCallResult(self.result, is_error=self.is_error)


class ClosingFailureTurn(FakeTurn):
    def __init__(self, tools: list[ProviderTool]) -> None:
        super().__init__(tools)
        self.exit_calls = 0

    def __exit__(self, exc_type, exc, traceback) -> None:
        self.exit_calls += 1
        raise OSError("close failed")


class UnavailableTurn:
    def __enter__(self):
        raise OSError("provider down")

    def __exit__(self, exc_type, exc, traceback) -> None:
        return None


class _StreamResponse:
    def __init__(self, lines: list[bytes]) -> None:
        self.lines = lines

    def __enter__(self):
        return iter(self.lines)

    def __exit__(self, exc_type, exc, traceback) -> None:
        return None


def _tool_config_raw(
    *,
    url: str = "http://localhost:8765/mcp",
    auth_env: str | None = None,
    max_rounds: int = 2,
) -> dict[str, Any]:
    raw = load_config_data("eval/fixtures/config.yaml")
    provider: dict[str, Any] = {
        "transport": "streamable_http",
        "url": url,
        "timeout_s": 3,
    }
    if auth_env:
        provider["auth_env"] = auth_env
    raw["tool_providers"] = {"house": provider}
    raw["domains"][0]["tools"] = {
        "provider": "house",
        "max_rounds": max_rounds,
        "allow": {
            "child": ["get_state", "light_on", "lock_open", "mystery"],
            "adult": [
                "get_state",
                "light_on",
                "light_off",
                "climate_set",
                "lock_open",
                "mystery",
            ],
        },
        "deny": ["light_off"],
    }
    return raw


def _tool_runtime(
    tmp_path: Path,
    adapter: ScriptedFakeAdapter,
    turn: Any,
    *,
    max_rounds: int = 2,
) -> PromptRuntime:
    raw = _tool_config_raw(max_rounds=max_rounds)
    raw["telemetry"] = _telemetry_raw(tmp_path)
    config = load_config_from_dict(raw)
    return PromptRuntime(
        config,
        adapter_factory=lambda model: adapter,
        tool_turn_factory=lambda provider: turn,
    )


def _telemetry_raw(tmp_path: Path) -> dict[str, Any]:
    return {
        "csv_path": str(tmp_path / "trace.csv"),
        "jsonl_path": str(tmp_path / "trace.jsonl"),
        "strict_mode": False,
    }


def _jsonl_events(tmp_path: Path) -> list[dict[str, Any]]:
    return [
        json.loads(line)
        for line in (tmp_path / "trace.jsonl").read_text(encoding="utf-8").splitlines()
    ]


def _provider_tool(name: str, annotations: dict[str, Any] | None) -> ProviderTool:
    return ProviderTool(
        provider="house",
        name=name,
        description=name,
        input_schema={"type": "object", "properties": {}},
        annotations=annotations,
    )


def _all_provider_tools() -> list[ProviderTool]:
    return [
        _provider_tool("get_state", {"readOnlyHint": True}),
        _provider_tool("light_on", {"destructiveHint": False}),
        _provider_tool("light_off", {"destructiveHint": False}),
        _provider_tool("climate_set", {"destructiveHint": False}),
        _provider_tool("lock_open", {"destructiveHint": True}),
        _provider_tool("mystery", None),
    ]


def _tool_response(name: str, arguments: str) -> dict[str, Any]:
    return {
        "text": "",
        "finish_reason": "tool_calls",
        "tool_calls": [
            {
                "id": f"call_{name}",
                "type": "function",
                "function": {"name": name, "arguments": arguments},
            }
        ],
    }


@contextmanager
def _running_provider(*, token: str):
    with socket.socket() as probe:
        probe.bind(("127.0.0.1", 0))
        port = probe.getsockname()[1]
    command = [
        sys.executable,
        "tests/fixtures/mcp_test_provider.py",
        "--port",
        str(port),
        "--token",
        token,
    ]
    process = subprocess.Popen(command, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    try:
        deadline = time.monotonic() + 10
        while time.monotonic() < deadline:
            if process.poll() is not None:
                pytest.fail("MCP test provider exited before becoming ready")
            try:
                with socket.create_connection(("127.0.0.1", port), timeout=0.1):
                    break
            except OSError:
                time.sleep(0.05)
        else:
            pytest.fail("MCP test provider did not become ready")
        yield f"http://127.0.0.1:{port}/mcp", token
    finally:
        process.terminate()
        try:
            process.wait(timeout=5)
        except subprocess.TimeoutExpired:
            process.kill()
            process.wait(timeout=5)
