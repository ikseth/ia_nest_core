"""ADR 0055: el marco en el turno y preguntar lo que falta.

Mismo modelo y proveedor falsos que las pruebas de ADR 0053 y 0054; los
ayudantes se repiten porque `tests/` no es un paquete.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import pytest

from ianest_core import service
from ianest_core.adapters import ScriptedFakeAdapter
from ianest_core.config import load_config, load_config_data, load_config_from_dict
from ianest_core.config.validator import validate_config_dict
from ianest_core.domain_router import DomainRouter
from ianest_core.errors import ConfigValidationError
from ianest_core.identity import Identity
from ianest_core.mcp_client import ToolCallResult
from ianest_core.registry import ModelRegistry, StaticAvailabilityProvider
from ianest_core.runtime import DomainRuntime, PromptRuntime
from ianest_core.tool_contracts import ProviderTool, offered_tools, parse_turn_context


ADULT = {"interlocutor_profile": "adult"}
NEEDS_PLACE = '{"needs": "place", "reason": "el tiempo depende del lugar"}'
NEEDS_NONE = '{"needs": null, "reason": "no depende"}'


def _frame(**overrides: Any) -> dict[str, Any]:
    frame = {
        "channel": "open_webui",
        "person": {"state": "known", "name": "Ana"},
        "device": {"state": "unknown"},
        "place": {"state": "unknown"},
        "language": "es",
        "missing": [],
    }
    frame.update(overrides)
    return frame


# --- criterio 1: sin marco, como v0.6.0 --------------------------------------


@pytest.mark.parametrize("turn_context", [None, {"trusted_providers": ["house"]}])
def test_without_frame_messages_and_trace_are_unchanged(tmp_path, turn_context) -> None:
    adapter = ScriptedFakeAdapter("fake_b", ["hola", "hola"])
    runtime, _ = _runtime(tmp_path, adapter)

    baseline = runtime.run(prompt="hola", domain_id="general")
    result = runtime.run(prompt="hola", domain_id="general", turn_context=turn_context)

    assert len(adapter.requests) == 2
    assert adapter.requests[1].messages == adapter.requests[0].messages
    assert set(result.trace) == set(baseline.trace)
    assert "frame_used" not in result.trace
    assert "input_required" not in result.trace
    done = _event(tmp_path, "done")["payload"]
    assert "frame_used" not in done and "frame_check" not in done


# --- criterio 2: missing vacio -----------------------------------------------


def test_frame_without_missing_makes_no_check_and_reaches_the_model(tmp_path) -> None:
    adapter = ScriptedFakeAdapter("fake_b", ["en Valdemoro no llueve"])
    runtime, _ = _runtime(tmp_path, adapter)
    frame = _frame(place={"state": "known", "home": "Casa", "locality": "Valdemoro"})

    result = runtime.run(
        prompt="va a llover?",
        domain_id="general",
        turn_context={"frame": frame},
    )

    assert len(adapter.requests) == 1
    messages = adapter.requests[0].messages
    assert messages[-1] == {"role": "user", "content": "va a llover?"}
    assert messages[-2]["role"] == "system"
    block = messages[-2]["content"]
    assert block.startswith("## marco de la conversacion")
    assert "Ana" in block and "Casa, Valdemoro" in block
    assert result.trace["frame_used"] is True
    assert "input_required" not in result.trace
    assert result.response == "en Valdemoro no llueve"


def test_stated_parts_reach_the_model_as_said_in_the_conversation(tmp_path) -> None:
    adapter = ScriptedFakeAdapter("fake_b", ["ok"])
    runtime, _ = _runtime(tmp_path, adapter)

    runtime.run(
        prompt="va a llover?",
        domain_id="general",
        turn_context={"frame": _frame(place={"state": "stated"}, stated={"place": "en Madrid"})},
    )

    assert "place (stated in this conversation): en Madrid" in adapter.requests[0].messages[-2]["content"]


# --- criterio 3: pregunta como resultado -------------------------------------


def test_missing_place_that_matters_is_asked_without_calling_the_model(tmp_path) -> None:
    adapter = ScriptedFakeAdapter("fake_b", [NEEDS_PLACE, "no deberia llegar"])
    runtime, _ = _runtime(tmp_path, adapter)

    result = runtime.run(
        prompt="va a llover?",
        domain_id="general",
        turn_context={"frame": _frame(missing=["place"])},
    )

    assert len(adapter.requests) == 1  # solo la clasificacion
    assert result.response == "De que lugar me preguntas?"
    assert result.trace["finish_reason"] == "input_required"
    assert result.trace["input_required"]["part"] == "place"
    assert result.trace["frame_used"] is True
    done = _event(tmp_path, "done")["payload"]
    assert done["finish_reason"] == "input_required"
    assert done["frame_check"]["needs"] == "place"
    assert isinstance(done["frame_check"]["latency_ms"], int)


def test_configured_question_and_language_fallback(tmp_path) -> None:
    raw = _raw(tmp_path)
    raw["frame_questions"] = {
        "default_language": "es",
        "place": {"es": "Donde estas?", "fr": "Ou es-tu?"},
    }
    adapter = ScriptedFakeAdapter("fake_b", [NEEDS_PLACE, NEEDS_PLACE, NEEDS_PLACE])
    runtime, _ = _runtime(tmp_path, adapter, raw)

    def ask(language: str | None) -> str:
        frame = _frame(missing=["place"], language=language)
        return runtime.run(prompt="tiempo?", domain_id="general", turn_context={"frame": frame}).response

    assert ask("fr-FR") == "Ou es-tu?"
    assert ask("de") == "Donde estas?"  # sin aleman: idioma por defecto
    assert ask(None) == "Donde estas?"


def test_stream_asks_as_content_without_new_event_types(tmp_path) -> None:
    adapter = ScriptedFakeAdapter("fake_b", [NEEDS_PLACE])
    runtime, _ = _runtime(tmp_path, adapter)

    events = list(
        runtime.stream(
            prompt="va a llover?",
            domain_id="general",
            turn_context={"frame": _frame(missing=["place"])},
        )
    )

    assert [event.type for event in events] == ["token", "done"]
    assert events[0].data["text"] == "De que lugar me preguntas?"
    done = events[-1].data
    assert done["finish_reason"] == "input_required"
    assert done["trace"]["input_required"]["part"] == "place"


# --- criterios 4 y 5: no pregunta --------------------------------------------


def test_missing_place_that_does_not_matter_is_answered(tmp_path) -> None:
    adapter = ScriptedFakeAdapter("fake_b", [NEEDS_NONE, "una bateria de litio es..."])
    runtime, _ = _runtime(tmp_path, adapter)

    result = runtime.run(
        prompt="que es una bateria de litio?",
        domain_id="general",
        turn_context={"frame": _frame(missing=["place"])},
    )

    assert len(adapter.requests) == 2
    assert result.response == "una bateria de litio es..."
    assert "input_required" not in result.trace
    assert _event(tmp_path, "done")["payload"]["frame_check"]["needs"] is None


@pytest.mark.parametrize(
    ("classifier", "expected"),
    [
        ('{"depends_on": "place", "said_in_request": false, "reason": "x"}', "place"),
        ('{"depends_on": "place", "said_in_request": true, "reason": "x"}', None),
        ('{"depends_on": null, "said_in_request": false, "reason": "x"}', None),
        (NEEDS_PLACE, "place"),
    ],
)
def test_two_judgements_ask_only_when_the_request_does_not_say_it(classifier, expected) -> None:
    from ianest_core.frame import parse_needs

    assert parse_needs(classifier, ("place", "person"))[0] == expected


@pytest.mark.parametrize(
    "classifier",
    [
        "basura sin json",
        '{"needs": "device", "reason": "x"}',
        '{"needs": "person", "reason": "no esta en missing"}',
        '["place"]',
    ],
)
def test_invalid_classifier_answers_never_ask(tmp_path, classifier: str) -> None:
    adapter = ScriptedFakeAdapter("fake_b", [classifier, "respuesta"])
    runtime, _ = _runtime(tmp_path, adapter)

    result = runtime.run(
        prompt="va a llover?",
        domain_id="general",
        turn_context={"frame": _frame(missing=["place", "device"])},
    )

    assert result.response == "respuesta"
    assert "input_required" not in result.trace


def test_failing_classifier_never_asks(tmp_path) -> None:
    adapter = _FailingFirstCall(ScriptedFakeAdapter("fake_b", ["respuesta"]))
    runtime, _ = _runtime(tmp_path, adapter)

    result = runtime.run(
        prompt="va a llover?",
        domain_id="general",
        turn_context={"frame": _frame(missing=["place"])},
    )

    assert result.response == "respuesta"
    assert "input_required" not in result.trace
    assert "classifier failed" in _event(tmp_path, "done")["payload"]["frame_check"]["reason"]


# --- criterio 6: el dispositivo no se pregunta -------------------------------


def test_only_device_missing_makes_no_check(tmp_path) -> None:
    adapter = ScriptedFakeAdapter("fake_b", ["hola"])
    runtime, _ = _runtime(tmp_path, adapter)

    result = runtime.run(
        prompt="hola",
        domain_id="general",
        turn_context={"frame": _frame(missing=["device"])},
    )

    assert len(adapter.requests) == 1
    assert "frame_check" not in _event(tmp_path, "done")["payload"]
    assert result.trace["frame_used"] is True


# --- criterio 7: preguntar antes de herramientas -----------------------------


def test_tool_domain_that_asks_opens_no_provider_and_classifies_no_effect(tmp_path) -> None:
    adapter = ScriptedFakeAdapter("fake_b", [NEEDS_PLACE])
    runtime, factory = _runtime(tmp_path, adapter)

    result = runtime.run(
        prompt="que temperatura hace?",
        domain_id="support",
        identity_override=ADULT,
        turn_context={"frame": _frame(missing=["place"])},
    )

    assert factory.opened == 0
    assert len(adapter.requests) == 1
    assert "effect" not in result.trace
    assert result.trace["finish_reason"] == "input_required"


# --- criterio 8: domain.route -------------------------------------------------


def test_domain_route_carries_hint_only_with_frame() -> None:
    config = load_config(Path("eval/fixtures/router.yaml"))
    router = DomainRouter(ModelRegistry(config, availability=StaticAvailabilityProvider()), config)
    frame = parse_turn_context(
        {"frame": _frame(place={"state": "known", "locality": "Valdemoro"}, missing=["device"])}
    ).frame

    plain = router._classification_prompt("va a llover?")
    hinted = router._classification_prompt("va a llover?", frame)

    assert "Conversation frame" not in plain
    assert "channel: open_webui; place: known, Valdemoro; missing: device" in hinted
    assert hinted.replace(hinted.splitlines()[-2] + "\n", "") == plain


def test_domain_route_accepts_turn_context_and_traces_frame_used() -> None:
    config = load_config(Path("eval/fixtures/router.yaml"))
    adapter = ScriptedFakeAdapter(
        "fake_router",
        ['{"domain": "general", "confidence": 0.9, "reason": "x"}'] * 2,
    )
    runtime = DomainRuntime(
        config,
        availability=StaticAvailabilityProvider(),
        adapter_factory=lambda _model: adapter,
    )

    with_frame = runtime.route(prompt="va a llover?", turn_context={"frame": _frame()})
    without = runtime.route(prompt="va a llover?")

    assert with_frame.trace["frame_used"] is True
    assert "frame_used" not in without.trace
    assert "Conversation frame" in adapter.requests[0].messages[-1]["content"]
    assert "Conversation frame" not in adapter.requests[1].messages[-1]["content"]


def test_capability_list_declares_turn_context_in_domain_route() -> None:
    catalog = service.list_capabilities()
    route = next(item for item in catalog["capabilities"] if item["name"] == "domain.route")
    assert "turn_context" in [param["name"] for param in route["params"]]


# --- criterio 9: restricted y child ------------------------------------------


def test_child_identity_is_restricted() -> None:
    assert Identity(interlocutor_profile="child").interlocutor_profile == "restricted"
    assert Identity(interlocutor_profile="restricted").interlocutor_profile == "restricted"
    with pytest.raises(ConfigValidationError):
        Identity(interlocutor_profile="kid")


@pytest.mark.parametrize("key", ["child", "restricted"])
def test_allow_with_child_or_restricted_offers_the_same(tmp_path, key: str) -> None:
    raw = _raw(tmp_path)
    raw["domains"][0]["tools"]["allow"] = {key: ["get_state", "light_on"]}
    validate_config_dict(raw)
    domain = load_config_from_dict(raw).domains[0]

    for profile in ("child", "restricted"):
        names = [tool.name for tool in offered_tools(domain, profile, _tools())]
        assert names == ["get_state", "light_on"]


def test_allow_with_child_and_restricted_is_a_config_error(tmp_path) -> None:
    raw = _raw(tmp_path)
    raw["domains"][0]["tools"]["allow"] = {"child": ["get_state"], "restricted": ["get_state"]}
    with pytest.raises(ConfigValidationError, match="child is the old name"):
        validate_config_dict(raw)


@pytest.mark.parametrize(
    "frame_questions",
    [
        "texto",
        {"place": {"es": ""}},
        {"device": {"es": "Que dispositivo?"}},
        {"default_language": 3},
    ],
)
def test_invalid_frame_questions_are_config_errors(tmp_path, frame_questions: Any) -> None:
    raw = _raw(tmp_path)
    raw["frame_questions"] = frame_questions
    with pytest.raises(ConfigValidationError):
        validate_config_dict(raw)


# --- criterio 10: forma del marco --------------------------------------------


@pytest.mark.parametrize(
    "frame",
    [
        "marco",
        {"channel": 3},
        {"place": "salon"},
        {"place": {"home": "Casa"}},
        {"place": {"state": "known", "extra": {"x": 1}}},
        {"missing": "place"},
        {"stated": {"place": 3}},
    ],
)
def test_invalid_frame_is_an_input_error(frame: Any) -> None:
    with pytest.raises(ConfigValidationError):
        parse_turn_context({"frame": frame})


def test_unknown_frame_fields_are_ignored() -> None:
    parsed = parse_turn_context({"frame": {"channel": "voz", "futuro": {"x": 1}}})
    assert parsed is not None and parsed.frame is not None
    assert parsed.frame.channel == "voz"
    assert parsed.frame.missing == ()


# --- ayudantes -----------------------------------------------------------------


class _Turn:
    def __init__(self, tools: list[ProviderTool]) -> None:
        self.tools = tools

    def list_tools(self) -> list[ProviderTool]:
        return list(self.tools)

    def call_tool(self, name: str, arguments: dict[str, Any]) -> ToolCallResult:
        return ToolCallResult(text="ok")


class _Factory:
    def __init__(self, tools: list[ProviderTool]) -> None:
        self.turn = _Turn(tools)
        self.opened = 0

    def __call__(self, provider):
        factory = self

        class _Manager:
            def __enter__(self):
                factory.opened += 1
                return factory.turn

            def __exit__(self, *args):
                return False

        return _Manager()


class _FailingFirstCall:
    def __init__(self, inner: ScriptedFakeAdapter) -> None:
        self.inner = inner
        self.calls = 0

    def stream(self, req):
        self.calls += 1
        if self.calls == 1:
            raise RuntimeError("router down")
        return self.inner.stream(req)


def _raw(tmp_path: Path) -> dict[str, Any]:
    raw = load_config_data("eval/fixtures/config.yaml")
    raw["tool_providers"] = {
        "house": {"transport": "streamable_http", "url": "http://localhost:8765/mcp", "timeout_s": 3}
    }
    raw["domains"][0]["tools"] = {
        "provider": "house",
        "max_rounds": 2,
        "allow": {"adult": ["get_state", "light_on"]},
        "deny": [],
    }
    raw["telemetry"] = {
        "csv_path": str(tmp_path / "trace.csv"),
        "jsonl_path": str(tmp_path / "trace.jsonl"),
        "strict_mode": False,
    }
    return raw


def _runtime(tmp_path: Path, adapter: Any, raw: dict[str, Any] | None = None):
    factory = _Factory(_tools())
    runtime = PromptRuntime(
        load_config_from_dict(raw or _raw(tmp_path)),
        adapter_factory=lambda model: adapter,
        tool_turn_factory=factory,
    )
    return runtime, factory


def _tools() -> list[ProviderTool]:
    def tool(name: str, annotations: dict[str, Any]) -> ProviderTool:
        return ProviderTool(
            provider="house",
            name=name,
            description=name,
            input_schema={"type": "object", "properties": {}},
            annotations=annotations,
        )

    return [
        tool("get_state", {"readOnlyHint": True}),
        tool("light_on", {"readOnlyHint": False, "destructiveHint": False}),
    ]


def _event(tmp_path: Path, name: str) -> dict[str, Any]:
    events = [
        json.loads(line)
        for line in (tmp_path / "trace.jsonl").read_text(encoding="utf-8").splitlines()
    ]
    return [event for event in events if event["event"] == name][-1]
