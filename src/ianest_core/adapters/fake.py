from __future__ import annotations

from typing import Any, Iterator

from ianest_core.adapters.base import Event, ModelRequest


class FakeAdapter:
    def __init__(self, model: str, response_text: str | None = None, finish_reason: str = "stop") -> None:
        self.model = model
        self.response_text = response_text
        self.finish_reason = finish_reason

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
                "finish_reason": self.finish_reason,
            },
        )


class ScriptedFakeAdapter:
    def __init__(
        self,
        model: str,
        responses: list[str | dict[str, Any]],
        finish_reason: str = "stop",
    ) -> None:
        self.model = model
        self.responses = responses
        self.finish_reason = finish_reason
        self.index = 0
        self.requests: list[ModelRequest] = []

    def stream(self, req: ModelRequest) -> Iterator[Event]:
        prompt = _last_user_message(req)
        self.requests.append(req)
        scripted = self._next_response()
        response = {"text": scripted} if isinstance(scripted, str) else dict(scripted)
        text = str(response.get("text", ""))
        if text:
            yield Event("token", {"text": text})
        done = {
            "text": text,
            "model": self.model,
            "tokens_in": _count_tokens(prompt),
            "tokens_out": _count_tokens(text),
            "finish_reason": response.get("finish_reason", self.finish_reason),
        }
        if "tool_calls" in response:
            done["tool_calls"] = list(response["tool_calls"])
        yield Event(
            "done",
            done,
        )

    def _next_response(self) -> str | dict[str, Any]:
        if not self.responses:
            return '{"output": "", "done": false}'
        if self.index >= len(self.responses):
            response = self.responses[-1]
        else:
            response = self.responses[self.index]
            self.index += 1
        return response


def _last_user_message(req: ModelRequest) -> str:
    for message in reversed(req.messages):
        if message.get("role") == "user":
            return message.get("content", "")
    return ""


def _count_tokens(text: str) -> int:
    return len(text.split()) if text else 0
