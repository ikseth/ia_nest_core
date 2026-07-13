from __future__ import annotations

from typing import Iterator

from ianest_core.adapters.base import Event, ModelRequest


class FakeAdapter:
    def __init__(self, model: str, response_text: str | None = None) -> None:
        self.model = model
        self.response_text = response_text

    def stream(self, req: ModelRequest) -> Iterator[Event]:
        prompt = _last_user_message(req)
        text = self.response_text
        if text is None:
            text = f"fake response from {self.model}: {prompt}"
        midpoint = max(1, len(text) // 2)
        yield Event("trace", {"adapter": "fake", "model": self.model})
        yield Event("token", {"text": text[:midpoint]})
        yield Event("token", {"text": text[midpoint:]})
        yield Event(
            "done",
            {
                "text": text,
                "model": self.model,
                "tokens_in": _count_tokens(prompt),
                "tokens_out": _count_tokens(text),
            },
        )


def _last_user_message(req: ModelRequest) -> str:
    for message in reversed(req.messages):
        if message.get("role") == "user":
            return message.get("content", "")
    return ""


def _count_tokens(text: str) -> int:
    return len(text.split()) if text else 0

