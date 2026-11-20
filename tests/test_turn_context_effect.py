"""ADR 0054: proveedores como techo y efecto de la peticion.

Usa el mismo proveedor y el mismo modelo falsos que las pruebas de ADR 0053
(`test_tool_contracts.py`); los ayudantes se repiten aqui porque `tests/` no es
un paquete.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import pytest
import yaml

from ianest_core import service
from ianest_core.adapters import ScriptedFakeAdapter
from ianest_core.config import load_config_data, load_config_from_dict
from ianest_core.errors import ConfigValidationError
from ianest_core.mcp_client import ToolCallResult
from ianest_core.runtime import PromptRuntime
from ianest_core.tool_contracts import ProviderTool, parse_effect_response, parse_turn_context


ORDER = '{"effect": "order", "reason": "pide encender"}'
READ = '{"effect": "read", "reason": "pide saber"}'
ADULT = {"interlocutor_profile": "adult"}


# --- techo e interseccion (D1, D2) -------------------------------------------


def test_without_turn_context_order_offers_what_v050_offered(tmp_path) -> None:
    adapter = ScriptedFakeAdapter("fake_b", [ORDER, "ok"])
    runtime, factory = _runtime(tmp_path, adapter)

    result = runtime.run(prompt="enciende la luz", domain_id="support", identity_override=ADULT)

    assert factory.opened == 1
    offered = _event(tmp_path, "tools_offered")["payload"]
    assert offered["tools"] == ["get_state", "light_on", "climate_set"]
    assert offered["effect"] == "order"
    assert "reason" not in offered
    assert result.trace["effect"] == "order"


def test_domain_without_tools_makes_no_classification_call(tmp_path) -> None:
    adapter = ScriptedFakeAdapter("fake_b", ["hola"])
    runtime, factory = _runtime(tmp_path, adapter)

    result = runtime.run(
        prompt="hola",
        domain_id="general",
        turn_context={"trusted_providers": []},
    )

    assert len(adapter.requests) == 1
    assert factory.opened == 0
    assert "effect" not in result.trace


@pytest.mark.parametrize("trusted", [[], ["otro"]])
def test_untrusted_provider_is_never_opened(tmp_path, trusted: list[str]) -> None:
    adapter = ScriptedFakeAdapter("fake_b", ["no puedo saberlo"])
    runtime, factory = _runtime(tmp_path, adapter)

    result = runtime.run(
        prompt="esta la luz encendida?",
        domain_id="support",
        identity_override=ADULT,
        turn_context={"trusted_providers": trusted},
    )

    assert factory.opened == 0
    assert len(adapter.requests) == 1  # ni clasificacion ni rondas
    assert adapter.requests[0].tools is None
    offered = _event(tmp_path, "tools_offered")["payload"]
    assert offered["tools"] == []
    assert offered["reason"] == "untrusted"
    assert "effect" not in result.trace


def test_trusted_name_outside_the_ceiling_adds_nothing(tmp_path) -> None:
    adapter = ScriptedFakeAdapter("fake_b", [ORDER, "ok"])
    runtime, factory = _runtime(tmp_path, adapter)

    runtime.run(
        prompt="enciende la luz",
        domain_id="support",
        identity_override=ADULT,
        turn_context={"trusted_providers": ["house", "fuera_del_techo"]},
    )

    assert factory.opened == 1
    assert factory.providers == ["house"]


def test_unknown_turn_context_parts_are_ignored() -> None:
    parsed = parse_turn_context({"frame": {"place": "salon"}, "catalog": {}})

    assert parsed is not None
    assert parsed.trusted_providers is None


@pytest.mark.parametrize(
    "raw",
    ["house", {"trusted_providers": "house"}, {"trusted_providers": [1]}, {"trusted_providers": [""]}],
)
def test_invalid_turn_context_is_an_input_error(raw: Any) -> None:
    with pytest.raises(ConfigValidationError):
        parse_turn_context(raw)


# --- efecto (D3, D4) ----------------------------------------------------------


def test_read_offers_only_read_only_tools_and_denies_forced_order(tmp_path) -> None:
    adapter = ScriptedFakeAdapter(
        "fake_b",
        [READ, _tool_response("light_on", '{"name":"salon"}'), "solo leo"],
    )
    runtime, factory = _runtime(tmp_path, adapter)

    result = runtime.run(
        prompt="que se esta viendo ahora en la tele del salon?",
        domain_id="support",
        identity_override=ADULT,
    )

    offered = _event(tmp_path, "tools_offered")["payload"]
    assert offered["tools"] == ["get_state"]
    assert offered["effect"] == "read"
    assert factory.turn.calls == []
    call = _event(tmp_path, "tool_call")["payload"]
    assert call["status"] == "denied"
    assert result.trace["effect"] == "read"
    advertised = [tool["function"]["name"] for tool in adapter.requests[1].tools]
    assert advertised == ["get_state"]


@pytest.mark.parametrize(
    "classifier",
    ["no se", "{not json", '{"effect": "write"}', '["order"]'],
)
def test_classifier_doubt_is_read(tmp_path, classifier: str) -> None:
    adapter = ScriptedFakeAdapter("fake_b", [classifier, "ok"])
    runtime, _ = _runtime(tmp_path, adapter)

    result = runtime.run(prompt="algo", domain_id="support", identity_override=ADULT)

    assert result.trace["effect"] == "read"
    assert _event(tmp_path, "tools_offered")["payload"]["tools"] == ["get_state"]


def test_classifier_failure_is_read(tmp_path) -> None:
    adapter = _FailingFirstCall(ScriptedFakeAdapter("fake_b", ["ok"]))
    runtime, _ = _runtime(tmp_path, adapter)

    result = runtime.run(prompt="algo", domain_id="support", identity_override=ADULT)

    assert result.trace["effect"] == "read"
    assert result.trace["effect_reason"].startswith("classifier failed")


def test_classification_uses_the_router_model_when_configured(tmp_path) -> None:
    router_adapter = ScriptedFakeAdapter("router", [ORDER])
    domain_adapter = ScriptedFakeAdapter("fake_b", ["ok"])
    raw = _raw(tmp_path)
    raw["router"] = {"model": "fake_b", "profile": "default"}  # `support` resuelve a fake_a

    def factory(model):
        return router_adapter if model.id == "fake_b" else domain_adapter

    runtime = PromptRuntime(
        load_config_from_dict(raw),
        adapter_factory=factory,
        tool_turn_factory=_Factory(_tools()),
    )
    result = runtime.run(prompt="enciende", domain_id="support", identity_override=ADULT)

    assert result.trace["effect"] == "order"
    assert len(router_adapter.requests) == 1
    assert "Decide the effect" in router_adapter.requests[0].messages[-1]["content"]
    assert all(
        "Decide the effect" not in str(request.messages) for request in domain_adapter.requests
    )


def test_stream_carries_effect_in_trace_and_no_new_event_type(tmp_path) -> None:
    adapter = ScriptedFakeAdapter("fake_b", [READ, "leido"])
    runtime, _ = _runtime(tmp_path, adapter)

    events = list(
        runtime.stream(
            prompt="esta encendida?",
            domain_id="support",
            identity_override=ADULT,
            turn_context={"trusted_providers": ["house"]},
        )
    )

    assert {event.type for event in events} == {"token", "done"}
    done = next(event for event in events if event.type == "done")
    assert done.data["trace"]["effect"] == "read"


def test_parse_effect_response_reads_json_inside_text() -> None:
    assert parse_effect_response('vale: {"effect": "order", "reason": "x"}') == ("order", "x")


# --- catalogo y tool_provider.list (D1, D5) -------------------------------------


@pytest.mark.parametrize("name", ["prompt.run", "prompt.stream"])
def test_catalog_declares_turn_context(name: str) -> None:
    entry = next(
        item for item in service.list_capabilities()["capabilities"] if item["name"] == name
    )
    assert "turn_context" in [param["name"] for param in entry["params"]]


def test_tool_provider_list_has_ids_and_domains_but_no_secrets(tmp_path) -> None:
    raw = _raw(tmp_path)
    raw["tool_providers"]["house"]["auth_env"] = "IANEST_TEST_SECRET_ENV"
    config_path = tmp_path / "core.yaml"
    config_path.write_text(yaml.safe_dump(raw), encoding="utf-8")

    result = service.list_tool_providers(config_path=config_path)

    assert result == {"tool_providers": [{"id": "house", "domains": ["support"]}]}
    text = json.dumps(result)
    assert "localhost" not in text
    assert "IANEST_TEST_SECRET_ENV" not in text
    assert "streamable_http" not in text


# --- ayudantes ------------------------------------------------------------------


class _Turn:
    def __init__(self, tools: list[ProviderTool]) -> None:
        self.tools = tools
        self.calls: list[tuple[str, dict[str, Any]]] = []

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc, traceback) -> None:
        return None

    def list_tools(self) -> list[ProviderTool]:
        return self.tools

    def call_tool(self, name: str, arguments: dict[str, Any]) -> ToolCallResult:
        self.calls.append((name, arguments))
        return ToolCallResult('{"ok": true}')


class _Factory:
    def __init__(self, tools: list[ProviderTool]) -> None:
        self.turn = _Turn(tools)
        self.opened = 0
        self.providers: list[str] = []

    def __call__(self, provider):
        self.opened += 1
        self.providers.append(provider.id)
        return self.turn


class _FailingFirstCall:
    def __init__(self, inner: ScriptedFakeAdapter) -> None:
        self.inner = inner
        self.calls = 0

    def stream(self, req):
        self.calls += 1
        if self.calls == 1:
            raise OSError("classifier down")
        return self.inner.stream(req)


def _raw(tmp_path: Path) -> dict[str, Any]:
    raw = load_config_data("eval/fixtures/config.yaml")
    raw["tool_providers"] = {
        "house": {"transport": "streamable_http", "url": "http://localhost:8765/mcp", "timeout_s": 3}
    }
    raw["domains"][0]["tools"] = {
        "provider": "house",
        "max_rounds": 2,
        "allow": {"adult": ["get_state", "light_on", "climate_set", "lock_open", "mystery"]},
        "deny": [],
    }
    raw["telemetry"] = {
        "csv_path": str(tmp_path / "trace.csv"),
        "jsonl_path": str(tmp_path / "trace.jsonl"),
        "strict_mode": False,
    }
    return raw


def _runtime(tmp_path: Path, adapter: Any) -> tuple[PromptRuntime, _Factory]:
    factory = _Factory(_tools())
    runtime = PromptRuntime(
        load_config_from_dict(_raw(tmp_path)),
        adapter_factory=lambda model: adapter,
        tool_turn_factory=factory,
    )
    return runtime, factory


def _tools() -> list[ProviderTool]:
    def tool(name: str, annotations: dict[str, Any] | None) -> ProviderTool:
        return ProviderTool(
            provider="house",
            name=name,
            description=name,
            input_schema={"type": "object", "properties": {}},
            annotations=annotations,
        )

    return [
        tool("get_state", {"readOnlyHint": True}),
        # como los scripts de la capa de Home Assistant (kodi_recomendar):
        tool("light_on", {"readOnlyHint": False, "destructiveHint": False}),
        tool("climate_set", {"destructiveHint": False}),
        tool("lock_open", {"destructiveHint": True}),
        tool("mystery", None),
    ]


def _tool_response(name: str, arguments: str) -> dict[str, Any]:
    return {
        "text": "",
        "finish_reason": "tool_calls",
        "tool_calls": [
            {"id": f"call_{name}", "type": "function", "function": {"name": name, "arguments": arguments}}
        ],
    }


def _event(tmp_path: Path, name: str) -> dict[str, Any]:
    events = [
        json.loads(line)
        for line in (tmp_path / "trace.jsonl").read_text(encoding="utf-8").splitlines()
    ]
    return next(event for event in events if event["event"] == name)
