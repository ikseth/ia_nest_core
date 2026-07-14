from __future__ import annotations

import json
import time
from dataclasses import dataclass
from typing import Any

from ianest_core.adapters import Event, ModelAdapter, ModelRequest, run_blocking
from ianest_core.config.schema import CoreConfig
from ianest_core.errors import CoreError
from ianest_core.registry import AvailabilityProvider
from ianest_core.runtime.prompt_runtime import PreparedPrompt, PromptRuntime
from ianest_core.telemetry import TelemetryWriter


@dataclass(frozen=True)
class ReasoningResult:
    output: str
    model: str
    domain: str
    stop_reason: str
    steps: list[dict[str, Any]]
    trace: dict[str, Any]

    def to_dict(self) -> dict[str, Any]:
        return {
            "output": self.output,
            "model": self.model,
            "domain": self.domain,
            "stop_reason": self.stop_reason,
            "steps": self.steps,
            "trace": self.trace,
        }


class ReasoningRuntime:
    def __init__(
        self,
        config: CoreConfig,
        telemetry: TelemetryWriter | None = None,
        availability: AvailabilityProvider | None = None,
        adapter: ModelAdapter | None = None,
    ) -> None:
        self.prompt_runtime = PromptRuntime(config, telemetry=telemetry, availability=availability)
        self.adapter = adapter

    def run(
        self,
        *,
        prompt: str,
        model_id: str | None = None,
        domain_id: str | None = None,
        identity_override: dict[str, str] | None = None,
        request_id: str | None = None,
    ) -> ReasoningResult:
        events = list(
            self.stream(
                prompt=prompt,
                model_id=model_id,
                domain_id=domain_id,
                identity_override=identity_override,
                request_id=request_id,
            )
        )
        done = next(event for event in reversed(events) if event.type == "done")
        data = done.data
        return ReasoningResult(
            output=str(data["output"]),
            model=str(data["model"]),
            domain=str(data["domain"]),
            stop_reason=str(data["stop_reason"]),
            steps=list(data["steps"]),
            trace=dict(data["trace"]),
        )

    def stream(
        self,
        *,
        prompt: str,
        model_id: str | None = None,
        domain_id: str | None = None,
        identity_override: dict[str, str] | None = None,
        request_id: str | None = None,
    ):
        prepared = self.prompt_runtime._prepare(
            prompt=prompt,
            model_id=model_id,
            domain_id=domain_id,
            identity_override=identity_override,
            request_id=request_id,
            capability="reasoning.run",
        )
        adapter = self.adapter or prepared.adapter
        max_iterations = int(prepared.params.get("max_iterations", 1) or 1)
        max_time_s = float(prepared.params.get("max_time_s", 0) or 0)
        max_context_tokens = int(prepared.params.get("max_context_tokens", 0) or 0)

        steps: list[dict[str, Any]] = []
        current_output = ""
        tokens_in = 0
        tokens_out = 0
        stop_reason = "max_iterations"

        for iteration in range(1, max_iterations + 1):
            req = _iteration_request(prompt, current_output, iteration, prepared)
            response = run_blocking(adapter, req)
            parsed = _parse_reasoning_response(response.text)
            current_output = parsed["output"]
            done = bool(parsed["done"])
            tokens_in += response.tokens_in
            tokens_out += response.tokens_out
            step = {"iteration": iteration, "output": current_output, "done": done}
            steps.append(step)
            self._record_step(prepared, step)
            yield Event("step", step)

            if done:
                stop_reason = "model_done"
                break
            if max_context_tokens and tokens_in + tokens_out >= max_context_tokens:
                stop_reason = "max_context_tokens"
                break
            if max_time_s and time.monotonic() - prepared.started >= max_time_s:
                stop_reason = "max_time"
                break
        else:
            stop_reason = "max_iterations"

        result = _done_payload(prepared, current_output, stop_reason, steps, tokens_in, tokens_out)
        self._record_done(prepared, result, tokens_in, tokens_out)
        yield Event("done", result)

    def _record_step(self, prepared: PreparedPrompt, step: dict[str, Any]) -> None:
        self.prompt_runtime.telemetry.record(
            request_id=prepared.request_id,
            event="step",
            capability="reasoning.run",
            identity=prepared.identity,
            payload=step,
            domain=prepared.domain,
            model=prepared.resolved.model.id,
            status="ok",
        )

    def _record_done(
        self,
        prepared: PreparedPrompt,
        payload: dict[str, Any],
        tokens_in: int,
        tokens_out: int,
    ) -> None:
        self.prompt_runtime.telemetry.record(
            request_id=prepared.request_id,
            event="done",
            capability="reasoning.run",
            identity=prepared.identity,
            payload=payload,
            domain=prepared.domain,
            model=prepared.resolved.model.id,
            latency_ms=payload["trace"]["latency_ms"],
            tokens_in=tokens_in,
            tokens_out=tokens_out,
            status="ok",
        )


def _iteration_request(prompt: str, current_output: str, iteration: int, prepared: PreparedPrompt) -> ModelRequest:
    if iteration == 1:
        content = (
            "Produce a draft answer. Return only JSON with keys output and done. "
            f"Prompt: {prompt}"
        )
    else:
        content = (
            "Critique and refine the current draft. Return only JSON with keys output and done. "
            f"Prompt: {prompt}\nCurrent draft: {current_output}"
        )
    messages = [message for message in prepared.req.messages if message.get("role") == "system"]
    messages.append({"role": "user", "content": content})
    return ModelRequest(messages=messages, params=prepared.params, extra=prepared.req.extra)


def _parse_reasoning_response(text: str) -> dict[str, Any]:
    try:
        payload = json.loads(text)
    except json.JSONDecodeError:
        return {"output": text, "done": False}
    if not isinstance(payload, dict):
        return {"output": text, "done": False}
    output = payload.get("output")
    done = payload.get("done")
    if not isinstance(output, str) or not isinstance(done, bool):
        return {"output": text, "done": False}
    return {"output": output, "done": done}


def _done_payload(
    prepared: PreparedPrompt,
    output: str,
    stop_reason: str,
    steps: list[dict[str, Any]],
    tokens_in: int,
    tokens_out: int,
) -> dict[str, Any]:
    latency_ms = int((time.monotonic() - prepared.started) * 1000)
    trace = {
        "request_id": prepared.request_id,
        "capability": "reasoning.run",
        "user_id": prepared.identity.user_id,
        "service": prepared.identity.service,
        "session_id": prepared.identity.session_id,
        "domain_tag": prepared.identity.domain_tag,
        "namespace": prepared.identity.namespace,
        "domain": prepared.domain,
        "model": prepared.resolved.model.id,
        "latency_ms": latency_ms,
        "tokens_in": tokens_in,
        "tokens_out": tokens_out,
        "status": "ok",
        "stop_reason": stop_reason,
    }
    return {
        "output": output,
        "model": prepared.resolved.model.id,
        "domain": prepared.domain,
        "stop_reason": stop_reason,
        "steps": steps,
        "trace": trace,
    }
