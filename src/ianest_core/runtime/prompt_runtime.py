from __future__ import annotations

import json
import logging
import time
from contextlib import AbstractContextManager, closing, nullcontext
from dataclasses import dataclass, replace
from typing import Any, Callable, Iterator
from uuid import uuid4

from ianest_core.adapters import (
    Event,
    FakeAdapter,
    ModelAdapter,
    ModelRequest,
    OpenAICompatibleAdapter,
    collect_events,
    run_blocking,
    split_reasoning,
)
from ianest_core.config.schema import CoreConfig, ModelConfig, ToolProviderConfig
from ianest_core.domain_router import DomainRouter
from ianest_core.errors import CoreError
from ianest_core.identity import Identity
from ianest_core.mcp_client import MCPClientTurn, ToolCallResult
from ianest_core.registry import AvailabilityProvider, ModelRegistry, ResolvedModel
from ianest_core.telemetry import TelemetryWriter
from ianest_core.tool_contracts import (
    ProviderTool,
    invocation_is_allowed,
    offered_tools,
)


ToolTurnFactory = Callable[[ToolProviderConfig], AbstractContextManager[Any]]


LOGGER = logging.getLogger(__name__)


@dataclass(frozen=True)
class PromptRunResult:
    response: str
    model: str
    domain: str
    params: dict[str, Any]
    trace: dict[str, Any]

    def to_dict(self) -> dict[str, Any]:
        return {
            "response": self.response,
            "model": self.model,
            "domain": self.domain,
            "params": self.params,
            "trace": self.trace,
        }


@dataclass(frozen=True)
class PreparedPrompt:
    started: float
    request_id: str
    resolved: ResolvedModel
    domain: str
    identity: Identity
    params: dict[str, Any]
    adapter: ModelAdapter
    req: ModelRequest
    capability: str
    trace_payload: dict[str, Any]


class PromptRuntime:
    def __init__(
        self,
        config: CoreConfig,
        telemetry: TelemetryWriter | None = None,
        availability: AvailabilityProvider | None = None,
        adapter_factory: Callable[[ModelConfig], ModelAdapter | None] | None = None,
        tool_turn_factory: ToolTurnFactory | None = None,
    ) -> None:
        self.config = config
        self.registry = ModelRegistry(config, availability=availability)
        self.router = DomainRouter(self.registry, config, adapter_factory=adapter_factory)
        self.telemetry = telemetry or TelemetryWriter(config.telemetry)
        self.adapter_factory = adapter_factory
        self.tool_turn_factory = tool_turn_factory or MCPClientTurn

    def run(
        self,
        *,
        prompt: str,
        model_id: str | None = None,
        domain_id: str | None = None,
        identity_override: dict[str, str] | None = None,
        request_id: str | None = None,
        trace_payload: dict[str, Any] | None = None,
        profile_id: str | None = None,
    ) -> PromptRunResult:
        prepared = self._prepare(
            prompt=prompt,
            model_id=model_id,
            domain_id=domain_id,
            identity_override=identity_override,
            request_id=request_id,
            capability="prompt.run",
            trace_payload=trace_payload,
            profile_id=profile_id,
        )

        try:
            if self._uses_tools(prepared):
                with closing(self._tool_loop_events(prepared)) as source:
                    response = collect_events(source)
            else:
                response = run_blocking(prepared.adapter, prepared.req)
        except CoreError as exc:
            self._record_error(prepared, exc.to_dict(), exc.type)
            raise

        latency_ms = _latency_ms(prepared.started)
        trace = _trace(
            prepared,
            latency_ms=latency_ms,
            tokens_in=response.tokens_in,
            tokens_out=response.tokens_out,
            finish_reason=response.finish_reason,
            tool_calls=response.turn_tool_calls,
        )
        done_payload = {
            "response": response.text,
            "finish_reason": response.finish_reason,
            **prepared.trace_payload,
        }
        if response.reasoning:
            done_payload["reasoning"] = response.reasoning
        self.telemetry.record(
            request_id=prepared.request_id,
            event="done",
            capability="prompt.run",
            identity=prepared.identity,
            payload=done_payload,
            domain=prepared.domain,
            model=prepared.resolved.model.id,
            latency_ms=latency_ms,
            tokens_in=response.tokens_in,
            tokens_out=response.tokens_out,
            status="ok",
        )
        return PromptRunResult(
            response=response.text,
            model=prepared.resolved.model.id,
            domain=prepared.domain,
            params=prepared.params,
            trace=trace,
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
        prepared = self._prepare(
            prompt=prompt,
            model_id=model_id,
            domain_id=domain_id,
            identity_override=identity_override,
            request_id=request_id,
            capability="prompt.run",
        )

        text_parts: list[str] = []
        tokens_in = 0
        tokens_out = 0
        finish_reason: Any = None
        adapter_reasoning = ""
        adapter_done: dict[str, Any] = {}
        completed = False
        source = (
            self._tool_loop_events(prepared)
            if self._uses_tools(prepared)
            else prepared.adapter.stream(prepared.req)
        )
        turn_tool_calls = 0
        source_context = closing(source) if self._uses_tools(prepared) else nullcontext(source)
        with source_context:
            for event in source:
                if event.type == "token":
                    text_parts.append(str(event.data.get("text", "")))
                elif event.type == "done":
                    tokens_in = int(event.data.get("tokens_in", 0) or 0)
                    tokens_out = int(event.data.get("tokens_out", 0) or 0)
                    finish_reason = event.data.get("finish_reason")
                    adapter_reasoning = str(event.data.get("reasoning", "") or "")
                    adapter_done = dict(event.data)
                    turn_tool_calls = int(adapter_done.pop("_turn_tool_calls", 0) or 0)
                    completed = True
                elif event.type == "error":
                    error_type = str(event.data.get("type", "AdapterError"))
                    self._record_error(prepared, event.data, error_type)
                    yield event
                    return

                if completed:
                    break
                yield event

        if not completed:
            return

        latency_ms = _latency_ms(prepared.started)
        final_text = str(adapter_done.get("text", "")) or "".join(text_parts)
        response_text, inline_reasoning = split_reasoning(final_text)
        reasoning = "\n".join(part for part in (adapter_reasoning, inline_reasoning) if part)
        trace = _trace(
            prepared,
            latency_ms=latency_ms,
            tokens_in=tokens_in,
            tokens_out=tokens_out,
            finish_reason=finish_reason,
            tool_calls=turn_tool_calls,
        )
        done_payload = {"response": response_text, "finish_reason": finish_reason}
        if reasoning:
            done_payload["reasoning"] = reasoning
        self.telemetry.record(
            request_id=prepared.request_id,
            event="done",
            capability="prompt.run",
            identity=prepared.identity,
            payload=done_payload,
            domain=prepared.domain,
            model=prepared.resolved.model.id,
            latency_ms=latency_ms,
            tokens_in=tokens_in,
            tokens_out=tokens_out,
            status="ok",
        )
        yield Event("done", {**adapter_done, "trace": trace})

    def _uses_tools(self, prepared: PreparedPrompt) -> bool:
        domain = prepared.resolved.domain
        return (
            not prepared.trace_payload
            and domain is not None
            and domain.tools is not None
        )

    def _tool_loop_events(self, prepared: PreparedPrompt) -> Iterator[Event]:
        domain = prepared.resolved.domain
        if domain is None or domain.tools is None:
            yield from prepared.adapter.stream(prepared.req)
            return
        policy = domain.tools
        provider = self.config.tool_providers[policy.provider]
        try:
            manager = self.tool_turn_factory(provider)
            turn = manager.__enter__()
        except CoreError:
            raise
        except Exception:
            self._record_tools_offered(prepared, provider.id, [])
            yield from self._provider_unavailable_events(prepared)
            return

        try:
            try:
                provider_tools = list(turn.list_tools())
            except CoreError:
                raise
            except Exception:
                self._record_tools_offered(prepared, provider.id, [])
                yield from self._provider_unavailable_events(prepared)
                return
            allowed = offered_tools(
                domain,
                prepared.identity.interlocutor_profile,
                provider_tools,
            )
            self._record_tools_offered(prepared, provider.id, allowed)
            yield from self._run_tool_rounds(
                prepared,
                turn,
                provider,
                provider_tools,
                allowed,
            )
        finally:
            try:
                manager.__exit__(None, None, None)
            except Exception:
                LOGGER.exception("MCP tool session close failed")

    def _provider_unavailable_events(self, prepared: PreparedPrompt) -> Iterator[Event]:
        messages = list(prepared.req.messages)
        note = {
            "role": "system",
            "content": (
                "The house tools are unavailable. Say so clearly and do not assume "
                "or invent any state."
            ),
        }
        messages.insert(max(0, len(messages) - 1), note)
        req = replace(prepared.req, messages=messages, tools=None)
        yield from _final_model_events(prepared.adapter.stream(req), 0, 0, 0)

    def _run_tool_rounds(
        self,
        prepared: PreparedPrompt,
        turn: Any,
        provider: ToolProviderConfig,
        provider_tools: list[ProviderTool],
        allowed: list[ProviderTool],
    ) -> Iterator[Event]:
        domain = prepared.resolved.domain
        assert domain is not None and domain.tools is not None
        messages = list(prepared.req.messages)
        advertised = [_openai_tool(tool) for tool in allowed]
        total_tokens_in = 0
        total_tokens_out = 0
        tool_call_count = 0

        for round_number in range(1, domain.tools.max_rounds + 1):
            req = replace(prepared.req, messages=list(messages), tools=advertised)
            round_done: dict[str, Any] | None = None
            for event in prepared.adapter.stream(req):
                if event.type == "done":
                    round_done = dict(event.data)
                    break
                yield event
            if round_done is None:
                return
            total_tokens_in += int(round_done.get("tokens_in", 0) or 0)
            total_tokens_out += int(round_done.get("tokens_out", 0) or 0)
            calls = list(round_done.get("tool_calls", []))
            if not calls:
                yield Event(
                    "done",
                    _final_done_data(
                        round_done,
                        total_tokens_in,
                        total_tokens_out,
                        tool_call_count,
                    ),
                )
                return

            messages.append(_assistant_tool_message(round_done, calls))
            at_limit = round_number == domain.tools.max_rounds
            for call in calls:
                tool_call_count += 1
                tool_message = self._handle_tool_call(
                    prepared=prepared,
                    turn=turn,
                    provider=provider,
                    provider_tools=provider_tools,
                    call=call,
                    call_number=tool_call_count,
                    at_limit=at_limit,
                )
                messages.append(tool_message)

            if at_limit:
                final_req = replace(prepared.req, messages=list(messages), tools=None)
                yield from _final_model_events(
                    prepared.adapter.stream(final_req),
                    total_tokens_in,
                    total_tokens_out,
                    tool_call_count,
                )
                return

    def _handle_tool_call(
        self,
        *,
        prepared: PreparedPrompt,
        turn: Any,
        provider: ToolProviderConfig,
        provider_tools: list[ProviderTool],
        call: dict[str, Any],
        call_number: int,
        at_limit: bool,
    ) -> dict[str, Any]:
        domain = prepared.resolved.domain
        assert domain is not None
        function = call.get("function") or {}
        name = str(function.get("name", ""))
        call_id = str(call.get("id") or f"call_{call_number}")
        raw_arguments = function.get("arguments", "{}")
        arguments: dict[str, Any] = {}
        arguments_payload: Any = raw_arguments
        arguments_error: BaseException | None = None
        status = "error"
        started = time.monotonic()

        try:
            parsed = json.loads(raw_arguments) if isinstance(raw_arguments, str) else raw_arguments
            if not isinstance(parsed, dict):
                raise ValueError("arguments must be a JSON object")
            arguments = parsed
            arguments_payload = parsed
        except (json.JSONDecodeError, TypeError, ValueError) as exc:
            arguments_error = exc

        if at_limit:
            status = "limit"
            result_text = f"limit: {name or 'tool'} was not invoked because max_rounds was reached"
        elif arguments_error is not None:
            result_text = (
                f"error: invalid arguments for {name or 'tool'}: "
                f"{_short_error(arguments_error)}"
            )
        else:
            if not invocation_is_allowed(
                domain,
                prepared.identity.interlocutor_profile,
                provider_tools,
                provider.id,
                name,
            ):
                status = "denied"
                result_text = f"denied: {name or 'tool'} is not allowed for this interlocutor"
            else:
                try:
                    result: ToolCallResult = turn.call_tool(name, arguments)
                    if result.is_error:
                        status = "error"
                        result_text = f"error: {name} failed: {_short_text(result.text)}"
                    else:
                        status = "invoked"
                        result_text = result.text
                except Exception as exc:
                    status = "error"
                    result_text = f"error: {name or 'tool'} failed: {_short_error(exc)}"

        self._record_tool_call(
            prepared=prepared,
            provider=provider.id,
            tool=name,
            arguments=arguments_payload,
            status=status,
            latency_ms=_latency_ms(started),
            result=result_text,
        )
        return {"role": "tool", "tool_call_id": call_id, "content": result_text}

    def _record_tools_offered(
        self,
        prepared: PreparedPrompt,
        provider: str,
        tools: list[ProviderTool],
    ) -> None:
        self.telemetry.record(
            request_id=prepared.request_id,
            event="tools_offered",
            capability=prepared.capability,
            identity=prepared.identity,
            payload={
                "provider": provider,
                "profile": prepared.identity.interlocutor_profile,
                "tools": [tool.name for tool in tools],
            },
            domain=prepared.domain,
            model=prepared.resolved.model.id,
        )

    def _record_tool_call(
        self,
        *,
        prepared: PreparedPrompt,
        provider: str,
        tool: str,
        arguments: Any,
        status: str,
        latency_ms: int,
        result: str,
    ) -> None:
        result_size_bytes, result_preview = _result_preview(result)
        self.telemetry.record(
            request_id=prepared.request_id,
            event="tool_call",
            capability=prepared.capability,
            identity=prepared.identity,
            payload={
                "provider": provider,
                "tool": tool,
                "arguments": arguments,
                "status": status,
                "latency_ms": latency_ms,
                "result_size_bytes": result_size_bytes,
                "result": result_preview,
            },
            domain=prepared.domain,
            model=prepared.resolved.model.id,
            latency_ms=latency_ms,
            status="ok",
        )

    def _prepare(
        self,
        *,
        prompt: str,
        model_id: str | None,
        domain_id: str | None,
        identity_override: dict[str, str] | None,
        request_id: str | None,
        capability: str = "prompt.run",
        trace_payload: dict[str, Any] | None = None,
        profile_id: str | None = None,
    ) -> PreparedPrompt:
        started = time.monotonic()
        request_id = request_id or str(uuid4())
        identity_data = dict(identity_override or {})
        Identity.from_defaults(self.config.identity_defaults, identity_data)
        route = None
        if model_id is None and domain_id is None:
            default_id = self.config.default_domain or "general"
            resolved = self.registry.resolve_prompt_target(None, default_id)
        else:
            resolved = self.registry.resolve_prompt_target(model_id, domain_id)
        domain = resolved.domain.id if resolved.domain is not None else ""
        if domain and not identity_data.get("domain_tag"):
            identity_data["domain_tag"] = domain
        identity = Identity.from_defaults(self.config.identity_defaults, identity_data)
        if profile_id is not None:
            resolved = ResolvedModel(
                model=resolved.model,
                domain=resolved.domain,
                profile=self.registry.profile(profile_id),
                substituted=resolved.substituted,
                preferred_model=resolved.preferred_model,
            )
        params = dict(resolved.profile.params)
        extra = dict(resolved.profile.extra)
        adapter = self._adapter_for(resolved.model)
        messages = _messages_with_system(prompt, resolved.profile.system)
        req = ModelRequest(messages=messages, params=params, extra=extra)

        self.telemetry.record(
            request_id=request_id,
            event="request_start",
            capability=capability,
            identity=identity,
            payload={"prompt": prompt, **(trace_payload or {})},
            domain=domain,
            model=resolved.model.id,
        )
        if route is not None or resolved.substituted:
            payload = route.to_dict() if route is not None else {}
            if resolved.substituted:
                payload = {
                    **payload,
                    "substituted": True,
                    "preferred_model": resolved.preferred_model,
                    "model": resolved.model.id,
                }
            self.telemetry.record(
                request_id=request_id,
                event="route",
                capability=capability,
                identity=identity,
                payload=payload,
                domain=domain,
                model=resolved.model.id,
            )
        self.telemetry.record(
            request_id=request_id,
            event="model_call",
            capability=capability,
            identity=identity,
            payload={"model_name": resolved.model.model_name, "adapter": resolved.model.adapter},
            domain=domain,
            model=resolved.model.id,
        )
        return PreparedPrompt(
            started=started,
            request_id=request_id,
            resolved=resolved,
            domain=domain,
            identity=identity,
            params=params,
            adapter=adapter,
            req=req,
            capability=capability,
            trace_payload=dict(trace_payload or {}),
        )

    def _record_error(self, prepared: PreparedPrompt, payload: dict[str, Any], error_type: str) -> None:
        self.telemetry.record(
            request_id=prepared.request_id,
            event="error",
            capability=prepared.capability,
            identity=prepared.identity,
            payload=payload,
            domain=prepared.domain,
            model=prepared.resolved.model.id,
            latency_ms=_latency_ms(prepared.started),
            status="error",
            error_type=error_type,
        )

    def _adapter_for(self, model: ModelConfig) -> ModelAdapter:
        if self.adapter_factory is not None:
            adapter = self.adapter_factory(model)
            if adapter is not None:
                return adapter
        if model.provider == "fake" or model.endpoint.startswith("fake://"):
            return FakeAdapter(model=model.id)
        return OpenAICompatibleAdapter(endpoint=model.endpoint, model_name=model.model_name)


def _latency_ms(started: float) -> int:
    return int((time.monotonic() - started) * 1000)


def _trace(
    prepared: PreparedPrompt,
    *,
    latency_ms: int,
    tokens_in: int,
    tokens_out: int,
    finish_reason: Any,
    tool_calls: int,
) -> dict[str, Any]:
    return {
        "request_id": prepared.request_id,
        "capability": "prompt.run",
        "user_id": prepared.identity.user_id,
        "service": prepared.identity.service,
        "session_id": prepared.identity.session_id,
        "domain_tag": prepared.identity.domain_tag,
        "namespace": prepared.identity.namespace,
        "interlocutor_profile": prepared.identity.interlocutor_profile,
        "domain": prepared.domain,
        "model": prepared.resolved.model.id,
        "latency_ms": latency_ms,
        "tokens_in": tokens_in,
        "tokens_out": tokens_out,
        "finish_reason": finish_reason,
        "tool_calls": tool_calls,
        "status": "ok",
        "substituted": prepared.resolved.substituted,
        "preferred_model": prepared.resolved.preferred_model,
    }


def _messages_with_system(prompt: str, system: str) -> list[dict[str, Any]]:
    messages: list[dict[str, Any]] = []
    if system:
        messages.append({"role": "system", "content": system})
    messages.append({"role": "user", "content": prompt})
    return messages


def _openai_tool(tool: ProviderTool) -> dict[str, Any]:
    return {
        "type": "function",
        "function": {
            "name": tool.name,
            "description": tool.description,
            "parameters": tool.input_schema,
        },
    }


def _assistant_tool_message(
    round_done: dict[str, Any],
    calls: list[dict[str, Any]],
) -> dict[str, Any]:
    return {
        "role": "assistant",
        "content": str(round_done.get("text", "")),
        "tool_calls": calls,
    }


def _final_model_events(
    events: Iterator[Event],
    prior_tokens_in: int,
    prior_tokens_out: int,
    tool_call_count: int,
) -> Iterator[Event]:
    for event in events:
        if event.type != "done":
            yield event
            continue
        done = dict(event.data)
        yield Event(
            "done",
            _final_done_data(
                done,
                prior_tokens_in + int(done.get("tokens_in", 0) or 0),
                prior_tokens_out + int(done.get("tokens_out", 0) or 0),
                tool_call_count,
            ),
        )
        return


def _final_done_data(
    done: dict[str, Any],
    tokens_in: int,
    tokens_out: int,
    tool_call_count: int,
) -> dict[str, Any]:
    return {
        **done,
        "tokens_in": tokens_in,
        "tokens_out": tokens_out,
        "_turn_tool_calls": tool_call_count,
    }


def _short_error(exc: BaseException) -> str:
    return _short_text(str(exc) or exc.__class__.__name__)


def _short_text(text: str, limit: int = 240) -> str:
    compact = " ".join(text.split())
    return compact if len(compact) <= limit else compact[: limit - 3] + "..."


def _result_preview(result: str) -> tuple[int, str]:
    encoded = result.encode("utf-8")
    preview = encoded[:2048]
    while preview:
        try:
            return len(encoded), preview.decode("utf-8")
        except UnicodeDecodeError:
            preview = preview[:-1]
    return len(encoded), ""
