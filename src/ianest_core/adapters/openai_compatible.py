from __future__ import annotations

import json
import os
from typing import Any, Iterator
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen

from ianest_core.adapters.base import Event, ModelRequest


class OpenAICompatibleAdapter:
    def __init__(self, endpoint: str, model_name: str, api_key: str | None = None) -> None:
        self.endpoint = endpoint
        self.model_name = model_name
        self.api_key = api_key if api_key is not None else os.environ.get("OPENAI_COMPAT_API_KEY", "")

    def stream(self, req: ModelRequest) -> Iterator[Event]:
        if not self.endpoint:
            yield Event("error", {"type": "AdapterError", "message": "empty endpoint", "field": "endpoint"})
            return

        body = {
            "model": self.model_name,
            "messages": req.messages,
            "stream": True,
            "stream_options": {"include_usage": True},
            **_public_params(req.params),
            **req.extra,
        }
        request = Request(
            _chat_completions_url(self.endpoint),
            data=json.dumps(body).encode("utf-8"),
            headers=self._headers(),
            method="POST",
        )

        text_parts: list[str] = []
        tokens_in = 0
        tokens_out = 0
        finish_reason: Any = None
        try:
            with urlopen(request, timeout=120) as response:
                for raw_line in response:
                    line = raw_line.decode("utf-8").strip()
                    if not line or not line.startswith("data:"):
                        continue
                    data = line.removeprefix("data:").strip()
                    if data == "[DONE]":
                        break
                    event = json.loads(data)
                    usage = event.get("usage") or {}
                    tokens_in = int(usage.get("prompt_tokens", tokens_in) or tokens_in)
                    tokens_out = int(usage.get("completion_tokens", tokens_out) or tokens_out)
                    for choice in event.get("choices", []):
                        if choice.get("finish_reason") is not None:
                            finish_reason = choice.get("finish_reason")
                        delta = choice.get("delta", {})
                        token = delta.get("content")
                        if token:
                            text_parts.append(token)
                            yield Event("token", {"text": token})
        except (HTTPError, URLError, TimeoutError, OSError, json.JSONDecodeError) as exc:
            yield Event("error", {"type": "AdapterError", "message": str(exc), "field": None})
            return

        text = "".join(text_parts)
        yield Event(
            "done",
            {
                "text": text,
                "model": self.model_name,
                "tokens_in": tokens_in,
                "tokens_out": tokens_out,
                "finish_reason": finish_reason,
            },
        )

    def _headers(self) -> dict[str, str]:
        headers = {"Content-Type": "application/json", "Accept": "text/event-stream"}
        if self.api_key:
            headers["Authorization"] = f"Bearer {self.api_key}"
        return headers


def _chat_completions_url(endpoint: str) -> str:
    clean = endpoint.rstrip("/")
    if clean.endswith("/chat/completions"):
        return clean
    return f"{clean}/chat/completions" if clean.endswith("/v1") else f"{clean}/v1/chat/completions"


def _public_params(params: dict[str, Any]) -> dict[str, Any]:
    blocked = {"max_iterations", "max_time_s", "max_context_tokens"}
    return {key: value for key, value in params.items() if key not in blocked}
