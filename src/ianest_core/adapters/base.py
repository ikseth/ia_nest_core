from __future__ import annotations

import re
from dataclasses import dataclass, field
from typing import Any, Iterator, Protocol

from ianest_core.errors import AdapterError, CoreError


@dataclass(frozen=True)
class Event:
    type: str
    data: dict[str, Any]


@dataclass(frozen=True)
class ModelRequest:
    messages: list[dict[str, str]]
    params: dict[str, Any] = field(default_factory=dict)
    extra: dict[str, Any] = field(default_factory=dict)


@dataclass(frozen=True)
class ModelResponse:
    text: str
    model: str
    tokens_in: int
    tokens_out: int
    finish_reason: Any = None
    reasoning: str = ""


class ModelAdapter(Protocol):
    def stream(self, req: ModelRequest) -> Iterator[Event]:
        ...


_THINK_BLOCK = re.compile(
    r"<\s*think\s*>(.*?)<\s*/\s*think\s*>",
    re.DOTALL,
)


def split_reasoning(text: str) -> tuple[str, str]:
    reasoning_parts: list[str] = []

    def collect(match: re.Match[str]) -> str:
        reasoning_parts.append(match.group(1))
        return ""

    clean_text = _THINK_BLOCK.sub(collect, text)
    return clean_text, "\n".join(reasoning_parts)


def run_blocking(adapter: ModelAdapter, req: ModelRequest) -> ModelResponse:
    text_parts: list[str] = []
    last_done: dict[str, Any] | None = None

    for event in adapter.stream(req):
        if event.type == "token":
            text_parts.append(str(event.data.get("text", "")))
        elif event.type == "done":
            last_done = event.data
            break
        elif event.type == "error":
            error_type = str(event.data.get("type", "AdapterError"))
            message = str(event.data.get("message", "adapter error"))
            field = event.data.get("field")
            if error_type == "AdapterError":
                raise AdapterError(message, field)
            raise CoreError(error_type, message, field)

    if last_done is None:
        raise AdapterError("adapter stream ended without done event")

    done_text = str(last_done.get("text", ""))
    text = done_text if done_text else "".join(text_parts)
    text, inline_reasoning = split_reasoning(text)
    reasoning = "\n".join(
        part
        for part in (str(last_done.get("reasoning", "") or ""), inline_reasoning)
        if part
    )
    return ModelResponse(
        text=text,
        model=str(last_done.get("model", "")),
        tokens_in=int(last_done.get("tokens_in", 0) or 0),
        tokens_out=int(last_done.get("tokens_out", 0) or 0),
        finish_reason=last_done.get("finish_reason"),
        reasoning=reasoning,
    )
