"""Marco de la conversacion en el turno (ADR 0055).

Extended compone el marco (extended ADR 0017) y lo manda resuelto en
`turn_context.frame`. El core lo usa como dato: pista al enrutar (D2), bloque
de contexto al responder (D3) y, si falta el lugar o la persona y la respuesta
depende de ello, pregunta como resultado declarado del turno (D4).
"""

from __future__ import annotations

import json
import re
from dataclasses import dataclass, field
from typing import Any

from ianest_core.errors import ConfigValidationError


FRAME_PARTS = ("person", "device", "place")
# Lo que se puede preguntar (D4): el dispositivo no se pregunta.
ASKABLE_PARTS = ("place", "person")
INPUT_REQUIRED = "input_required"

DEFAULT_LANGUAGE = "en"
DEFAULT_FRAME_QUESTIONS: dict[str, dict[str, str]] = {
    "place": {
        "en": "Which place are you asking about?",
        "es": "De que lugar me preguntas?",
    },
    "person": {
        "en": "Who am I talking to?",
        "es": "Con quien hablo?",
    },
}


@dataclass(frozen=True)
class Frame:
    channel: str | None = None
    person: dict[str, Any] | None = None
    device: dict[str, Any] | None = None
    place: dict[str, Any] | None = None
    language: str | None = None
    missing: tuple[str, ...] = ()
    stated: dict[str, str] = field(default_factory=dict)

    def askable_missing(self) -> tuple[str, ...]:
        return tuple(part for part in ASKABLE_PARTS if part in self.missing)


def parse_frame(raw: Any) -> Frame | None:
    """Valida `turn_context.frame`. Campos desconocidos se ignoran."""
    if raw is None:
        return None
    if not isinstance(raw, dict):
        _invalid("frame", "must be an object")
    values: dict[str, Any] = {}
    for name in ("channel", "language"):
        if name in raw:
            value = raw[name]
            if value is not None and not isinstance(value, str):
                _invalid(name, "must be a string or null")
            values[name] = value
    for name in FRAME_PARTS:
        if name in raw:
            values[name] = _parse_part(name, raw[name])
    if "missing" in raw:
        missing = raw["missing"]
        if not isinstance(missing, list) or not all(isinstance(item, str) for item in missing):
            _invalid("missing", "must be a list of strings")
        values["missing"] = tuple(missing)
    if "stated" in raw:
        stated = raw["stated"]
        if not isinstance(stated, dict) or not all(
            isinstance(key, str) and isinstance(value, str) for key, value in stated.items()
        ):
            _invalid("stated", "must be an object of strings")
        values["stated"] = dict(stated)
    return Frame(**values)


def _parse_part(name: str, raw: Any) -> dict[str, Any]:
    if not isinstance(raw, dict):
        _invalid(name, "must be an object")
    if not isinstance(raw.get("state"), str):
        _invalid(f"{name}.state", "must be a string")
    for key, value in raw.items():
        if value is not None and not isinstance(value, (str, bool)):
            _invalid(f"{name}.{key}", "must be a string, a boolean or null")
    return dict(raw)


def _invalid(name: str, message: str) -> None:
    raise ConfigValidationError(
        f"turn_context.frame.{name} {message}" if name != "frame" else f"turn_context.frame {message}",
        f"turn_context.frame.{name}" if name != "frame" else "turn_context.frame",
    )


# --- D2: pista al enrutar -------------------------------------------------


def router_hint(frame: Frame) -> str:
    place = frame.place or {}
    place_text = str(place.get("state", "unknown"))
    if place.get("locality"):
        place_text += f", {place['locality']}"
    missing = ", ".join(frame.missing) if frame.missing else "nothing"
    return (
        "Conversation frame (a hint, not a rule): "
        f"channel: {frame.channel or 'unknown'}; place: {place_text}; missing: {missing}."
    )


# --- D3: contexto al responder --------------------------------------------


def frame_context_block(frame: Frame) -> str:
    person = frame.person or {}
    device = frame.device or {}
    place = frame.place or {}
    lines = ["## marco de la conversacion", f"- channel: {frame.channel or 'unknown'}"]
    lines.append(f"- speaking: {person.get('name') or 'unknown'}")
    if device.get("name"):
        shared = " (shared)" if device.get("shared") is True else ""
        lines.append(f"- device: {device['name']}{shared}")
    else:
        lines.append("- device: unknown")
    if place.get("home") or place.get("locality") or place.get("timezone"):
        details = [
            str(place[key])
            for key in ("home", "locality", "timezone")
            if place.get(key)
        ]
        lines.append(f"- place: {', '.join(details)}")
    else:
        lines.append("- place: unknown")
    if frame.language:
        lines.append(f"- language: {frame.language}")
    for part, value in sorted(frame.stated.items()):
        lines.append(f"- {part} (stated in this conversation): {value}")
    return "\n".join(lines)


# --- D4: preguntar lo que falta -------------------------------------------

_PART_RULES = {
    "place": (
        'Answer "place" when a correct answer needs to know WHERE the speaker is: '
        "weather, rain, outside temperature, local time, sunrise, what is open or near, "
        "traffic, local news. "
        'Examples: "will it rain?" -> place; "what is the temperature?" -> place; '
        '"what time is it?" -> place; "is the pharmacy open?" -> place.'
    ),
    "person": (
        'Answer "person" when a correct answer needs to know WHO is speaking: their '
        "agenda, reminders, messages, preferences, belongings or relatives. "
        'Examples: "what do I have today?" -> person; "what is my favourite film?" -> person.'
    ),
}
_NULL_RULE = (
    "Answer null when the answer is the same wherever and whoever asks: general "
    "knowledge, explanations, definitions, maths, stories, jokes, greetings. "
    'Examples: "what is a lithium battery?" -> null; "why does it rain?" -> null; '
    '"tell me a story" -> null; "hello" -> null.'
)


def needs_prompt(text: str, askable: tuple[str, ...]) -> str:
    """Prompt de la clasificacion de D4; solo nombra las partes que faltan.

    Dos juicios separados (de que depende y si la peticion ya lo dice): un
    modelo pequeno acierta mejor cada uno por separado que el compuesto.
    """
    options = " or ".join(f'"{part}"' for part in askable)
    rules = " ".join(_PART_RULES[part] for part in askable)
    return (
        "Some facts about the conversation are unknown. Decide two things about "
        "the request. "
        f"1) depends_on: {rules} {_NULL_RULE} "
        "2) said_in_request: true if the request itself names that fact (a city, "
        'a country or a place for "place"; a name for "person"), otherwise false. '
        "Judge only the request itself, not any context around it. "
        f'Return only JSON: {{"depends_on": {options} or null, '
        '"said_in_request": true or false, "reason": "why, in a few words"}}.\n'
        f"Request: {text}"
    )


def parse_needs(text: str, askable: tuple[str, ...]) -> tuple[str | None, str]:
    """Parte que hay que preguntar, o `None` (cualquier respuesta no valida)."""
    match = re.search(r"\{.*\}", text or "", re.DOTALL)
    if match is None:
        return None, "classifier response is not JSON"
    try:
        data = json.loads(match.group(0))
    except json.JSONDecodeError:
        return None, "classifier response is not JSON"
    if not isinstance(data, dict):
        return None, "classifier response is not an object"
    needs = data.get("depends_on", data.get("needs"))
    reason = data.get("reason")
    reason_text = str(reason)[:200] if reason else ""
    if needs is None:
        return None, reason_text
    if needs not in askable:
        return None, f"not askable {needs!r}"
    if data.get("said_in_request") is True:
        return None, f"{needs} said in the request"
    return str(needs), reason_text


@dataclass(frozen=True)
class FrameQuestions:
    default_language: str = DEFAULT_LANGUAGE
    texts: dict[str, dict[str, str]] = field(default_factory=dict)

    def question(self, part: str, language: str | None) -> str:
        texts = {**DEFAULT_FRAME_QUESTIONS.get(part, {}), **self.texts.get(part, {})}
        for candidate in _language_candidates(language) + _language_candidates(self.default_language):
            if candidate in texts:
                return texts[candidate]
        if DEFAULT_LANGUAGE in texts:
            return texts[DEFAULT_LANGUAGE]
        return next(iter(texts.values()))


def _language_candidates(language: str | None) -> list[str]:
    if not language:
        return []
    lowered = language.strip().lower()
    base = re.split(r"[-_]", lowered, maxsplit=1)[0]
    return [lowered, base] if base != lowered else [lowered]
