from __future__ import annotations

import json
import os
from contextlib import ExitStack
from dataclasses import dataclass
from datetime import timedelta
from typing import Any

from ianest_core.config.schema import ToolProviderConfig
from ianest_core.errors import ConfigValidationError
from ianest_core.tool_contracts import ProviderTool


@dataclass(frozen=True)
class ToolCallResult:
    text: str
    is_error: bool = False


class MCPClientTurn:
    def __init__(self, provider: ToolProviderConfig) -> None:
        self.provider = provider
        self._stack: ExitStack | None = None
        self._portal: Any = None
        self._session: Any = None

    def __enter__(self) -> MCPClientTurn:
        try:
            import httpx
            from anyio.from_thread import start_blocking_portal
            from mcp import ClientSession
            from mcp.client.streamable_http import streamable_http_client
        except ImportError as exc:
            raise ConfigValidationError(
                "MCP extra not installed; install ianest-core[interfaces]",
                "tools",
            ) from exc

        headers: dict[str, str] = {}
        if self.provider.auth_env:
            token = os.environ.get(self.provider.auth_env, "")
            if not token:
                raise ConfigValidationError(
                    "tool provider auth environment variable is not resolved",
                    f"tool_providers.{self.provider.id}.auth_env",
                )
            headers["Authorization"] = f"Bearer {token}"

        stack = ExitStack()
        try:
            self._portal = stack.enter_context(
                start_blocking_portal(name=f"ianest-mcp-{self.provider.id}")
            )
            http_client = stack.enter_context(
                self._portal.wrap_async_context_manager(
                    httpx.AsyncClient(headers=headers, timeout=self.provider.timeout_s)
                )
            )
            read_stream, write_stream, _ = stack.enter_context(
                self._portal.wrap_async_context_manager(
                    streamable_http_client(
                        self.provider.url,
                        http_client=http_client,
                        terminate_on_close=True,
                    )
                )
            )
            self._session = stack.enter_context(
                self._portal.wrap_async_context_manager(
                    ClientSession(
                        read_stream,
                        write_stream,
                        read_timeout_seconds=timedelta(seconds=self.provider.timeout_s),
                    )
                )
            )
            self._portal.call(self._session.initialize)
        except BaseException:
            stack.close()
            raise
        self._stack = stack
        return self

    def __exit__(self, exc_type: Any, exc: Any, traceback: Any) -> None:
        if self._stack is not None:
            self._stack.close()
        self._stack = None
        self._portal = None
        self._session = None

    def list_tools(self) -> list[ProviderTool]:
        self._require_open()
        tools: list[ProviderTool] = []
        cursor: str | None = None
        while True:
            result = self._portal.call(self._session.list_tools, cursor)
            tools.extend(self._normalize_tool(tool) for tool in result.tools)
            cursor = result.nextCursor
            if not cursor:
                return tools

    def call_tool(self, name: str, arguments: dict[str, Any]) -> ToolCallResult:
        self._require_open()
        result = self._portal.call(
            self._session.call_tool,
            name,
            arguments,
            timedelta(seconds=self.provider.timeout_s),
        )
        return ToolCallResult(text=_tool_result_text(result), is_error=bool(result.isError))

    def _normalize_tool(self, tool: Any) -> ProviderTool:
        annotations = None
        if tool.annotations is not None:
            annotations = tool.annotations.model_dump(by_alias=True, exclude_none=True)
        return ProviderTool(
            provider=self.provider.id,
            name=str(tool.name),
            description=str(tool.description or ""),
            input_schema=dict(tool.inputSchema),
            annotations=annotations,
        )

    def _require_open(self) -> None:
        if self._portal is None or self._session is None:
            raise RuntimeError("MCP client turn is not open")


def _tool_result_text(result: Any) -> str:
    if result.structuredContent is not None:
        return json.dumps(result.structuredContent, ensure_ascii=False, sort_keys=True)
    parts: list[str] = []
    for item in result.content:
        if getattr(item, "type", None) == "text":
            parts.append(str(item.text))
        else:
            parts.append(
                json.dumps(
                    item.model_dump(by_alias=True, exclude_none=True),
                    ensure_ascii=False,
                    sort_keys=True,
                )
            )
    return "\n".join(parts)
