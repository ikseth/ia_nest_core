from __future__ import annotations

import json
import re
from dataclasses import dataclass, field
from typing import Any

from ianest_core.config.schema import DomainConfig
from ianest_core.errors import ConfigValidationError
from ianest_core.frame import Frame, parse_frame
from ianest_core.identity import normalize_profile
from ianest_core.turn_context_blocks import ContextBlock


# Efecto de la peticion (ADR 0054, D3-D4): solo resta de lo permitido.
EFFECT_READ = "read"
EFFECT_ORDER = "order"
EFFECTS = (EFFECT_READ, EFFECT_ORDER)


@dataclass(frozen=True)
class ProviderTool:
    provider: str
    name: str
    description: str = ""
    input_schema: dict[str, Any] = field(default_factory=dict)
    annotations: dict[str, Any] | None = None


@dataclass(frozen=True)
class TurnContext:
    """Contexto del turno que compone extended (ADR 0054, D1).

    Es dato, no instruccion. `trusted_providers` no llega al modelo; en
    `None` significa que la parte no vino (comportamiento de `v0.5.0`); una
    tupla vacia es un dato: no hay nada confiado. `frame` es el marco de la
    conversacion (ADR 0055, D1): llega al modelo como dato; `None` si no vino.
    `context` son los bloques separados de la frase (ADR 0056, D1).
    """

    trusted_providers: tuple[str, ...] | None = None
    frame: Frame | None = None
    context: tuple[ContextBlock, ...] | None = None


def parse_turn_context(raw: Any) -> TurnContext | None:
    """Valida `turn_context`. Partes desconocidas se ignoran (H13)."""
    if raw is None:
        return None
    if isinstance(raw, TurnContext):
        return raw
    if not isinstance(raw, dict):
        raise ConfigValidationError("turn_context must be an object", "turn_context")
    trusted: tuple[str, ...] | None = None
    if "trusted_providers" in raw:
        value = raw["trusted_providers"]
        if not isinstance(value, list) or not all(
            isinstance(item, str) and item for item in value
        ):
            raise ConfigValidationError(
                "turn_context.trusted_providers must be a list of non-empty strings",
                "turn_context.trusted_providers",
            )
        trusted = tuple(value)
    context: tuple[ContextBlock, ...] | None = None
    if "context" in raw:
        value = raw["context"]
        if not isinstance(value, list):
            raise ConfigValidationError(
                "turn_context.context must be a list", "turn_context.context"
            )
        blocks: list[ContextBlock] = []
        for index, block in enumerate(value):
            field = f"turn_context.context.{index}"
            if not isinstance(block, dict):
                raise ConfigValidationError(f"{field} must be an object", field)
            origin = block.get("origin")
            text = block.get("text")
            if not isinstance(origin, str):
                raise ConfigValidationError(f"{field}.origin must be a string", f"{field}.origin")
            if not isinstance(text, str):
                raise ConfigValidationError(f"{field}.text must be a string", f"{field}.text")
            if text.strip():
                blocks.append(ContextBlock(origin=origin, text=text))
        context = tuple(blocks)
    return TurnContext(
        trusted_providers=trusted,
        frame=parse_frame(raw.get("frame")),
        context=context,
    )


def provider_is_trusted(turn_context: TurnContext | None, provider_id: str) -> bool:
    """Interseccion del techo (`tool_providers`) con lo confiado (D2).

    Quien llama ya resolvio el proveedor desde `tool_providers`, asi que un
    nombre confiado fuera del techo nunca llega aqui: la memoria solo resta.
    """
    if turn_context is None or turn_context.trusted_providers is None:
        return True
    return provider_id in turn_context.trusted_providers


def tool_fits_effect(tool: ProviderTool, effect: str) -> bool:
    """Con `read` solo pasan las de `readOnlyHint: true`; con `order`, todas."""
    if effect == EFFECT_ORDER:
        return True
    return bool(tool.annotations) and tool.annotations.get("readOnlyHint") is True


def effect_classification_prompt(text: str) -> str:
    return (
        "Decide the effect of the user's request on the house. "
        "Answer 'read' if it asks to know, check or query something; "
        "answer 'order' only if it explicitly asks to change, start, stop, "
        "turn on/off, set or play something. If in doubt, answer 'read'. "
        'Return only JSON: {"effect": "read" or "order", "reason": "short"}.\n'
        f"Request: {text}"
    )


def parse_effect_response(text: str) -> tuple[str, str]:
    """Efecto y motivo; cualquier respuesta no valida es `read` (en la duda)."""
    match = re.search(r"\{.*\}", text or "", re.DOTALL)
    if match is None:
        return EFFECT_READ, "classifier response is not JSON"
    try:
        data = json.loads(match.group(0))
    except json.JSONDecodeError:
        return EFFECT_READ, "classifier response is not JSON"
    if not isinstance(data, dict):
        return EFFECT_READ, "classifier response is not an object"
    effect = data.get("effect")
    if effect not in EFFECTS:
        return EFFECT_READ, f"unknown effect {effect!r}"
    reason = data.get("reason")
    return effect, str(reason)[:200] if reason else ""


def offered_tools(
    domain: DomainConfig,
    interlocutor_profile: str,
    provider_tools: list[ProviderTool],
    effect: str = EFFECT_ORDER,
) -> list[ProviderTool]:
    return [
        tool
        for tool in provider_tools
        if tool_is_allowed(domain, interlocutor_profile, tool)
        and tool_fits_effect(tool, effect)
    ]


def tool_is_allowed(
    domain: DomainConfig,
    interlocutor_profile: str,
    tool: ProviderTool,
) -> bool:
    policy = domain.tools
    if policy is None or not interlocutor_profile:
        return False
    if tool.provider != policy.provider:
        return False
    allowed_names = policy.allow.get(normalize_profile(interlocutor_profile))
    if allowed_names is None or tool.name not in allowed_names:
        return False
    if tool.name in policy.deny:
        return False
    return _is_non_destructive(tool.annotations)


def invocation_is_allowed(
    domain: DomainConfig,
    interlocutor_profile: str,
    provider_tools: list[ProviderTool],
    provider: str,
    tool_name: str,
    effect: str = EFFECT_ORDER,
) -> bool:
    tool = next(
        (
            item
            for item in provider_tools
            if item.provider == provider and item.name == tool_name
        ),
        None,
    )
    return (
        tool is not None
        and tool_is_allowed(domain, interlocutor_profile, tool)
        and tool_fits_effect(tool, effect)
    )


def _is_non_destructive(annotations: dict[str, Any] | None) -> bool:
    if not annotations:
        return False
    return annotations.get("readOnlyHint") is True or annotations.get("destructiveHint") is False
