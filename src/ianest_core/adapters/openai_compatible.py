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
        if req.tools is not None:
            body["tools"] = req.tools
        request = Request(
            _chat_completions_url(self.endpoint),
            data=json.dumps(body).encode("utf-8"),
            headers=self._headers(),
            method="POST",
        )

        text_parts: list[str] = []
        reasoning_parts: list[str] = []
        tokens_in = 0
        tokens_out = 0
        finish_reason: Any = None
        tool_call_parts: list[tuple[int, dict[str, Any]]] = []
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
                        reasoning = (
                            delta.get("reasoning_content")
                            if "reasoning_content" in delta
                            else delta.get("reasoning")
                        )
                        if reasoning:
                            reasoning_parts.append(str(reasoning))
                        token = delta.get("content")
                        if token:
                            text_parts.append(token)
                            yield Event("token", {"text": token})
                        for fragment in delta.get("tool_calls") or []:
                            _accumulate_tool_call(tool_call_parts, fragment)
        except (HTTPError, URLError, TimeoutError, OSError, json.JSONDecodeError) as exc:
            yield Event("error", {"type": "AdapterError", "message": str(exc), "field": None})
            return

        text = "".join(text_parts)
        if finish_reason is None:
            finish_reason = "incomplete"
        done = {
            "text": text,
            "model": self.model_name,
            "tokens_in": tokens_in,
            "tokens_out": tokens_out,
            "finish_reason": finish_reason,
            "reasoning": "".join(reasoning_parts),
        }
        if tool_call_parts:
            done["tool_calls"] = [call for _, call in tool_call_parts]
        yield Event("done", done)

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


def _accumulate_tool_call(
    parts: list[tuple[int, dict[str, Any]]], fragment: dict[str, Any]
) -> None:
    index = int(fragment.get("index", 0) or 0)
    fragment_id = str(fragment["id"]) if fragment.get("id") else ""
    current: dict[str, Any] | None = None
    for candidate_index, candidate in reversed(parts):
        if candidate_index != index:
            continue
        if not fragment_id or not candidate["id"] or candidate["id"] == fragment_id:
            current = candidate
        break
    if current is None:
        current = {"id": "", "type": "function", "function": {"name": "", "arguments": ""}}
        parts.append((index, current))
    if fragment_id:
        current["id"] = fragment_id
    if fragment.get("type"):
        current["type"] = str(fragment["type"])
    function = fragment.get("function") or {}
    if function.get("name"):
        current["function"]["name"] += str(function["name"])
    if function.get("arguments"):
        current["function"]["arguments"] += str(function["arguments"])
