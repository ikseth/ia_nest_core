#!/usr/bin/env python3
"""MCP test provider with in-memory home state.

Purpose: exercise ADR 0053 through a real streamable HTTP MCP server.
Inputs: --port and optional --token command-line arguments.
Outputs: MCP tool responses over localhost HTTP.
Effects: keeps light, climate and lock state in process memory.
Requirements: the interfaces extra (mcp and uvicorn).
Security: test-only server; bind it to localhost and never use real secrets.
"""

from __future__ import annotations

import argparse
from typing import Any


STATE: dict[str, Any] = {
    "lights": {},
    "climate": {},
    "locks": {},
}


def create_server(*, host: str, port: int):
    from mcp.server.fastmcp import FastMCP
    from mcp.types import ToolAnnotations

    server = FastMCP("ianest-mcp-test-provider", host=host, port=port)

    @server.tool(annotations=ToolAnnotations(readOnlyHint=True), structured_output=True)
    def get_state() -> dict[str, Any]:
        """Return the complete in-memory test state."""
        return {
            "lights": dict(STATE["lights"]),
            "climate": dict(STATE["climate"]),
            "locks": dict(STATE["locks"]),
        }

    @server.tool(annotations=ToolAnnotations(destructiveHint=False), structured_output=True)
    def light_on(name: str) -> dict[str, Any]:
        """Turn on a named test light."""
        STATE["lights"][name] = True
        return {"name": name, "on": True}

    @server.tool(annotations=ToolAnnotations(destructiveHint=False), structured_output=True)
    def light_off(name: str) -> dict[str, Any]:
        """Turn off a named test light."""
        STATE["lights"][name] = False
        return {"name": name, "on": False}

    @server.tool(annotations=ToolAnnotations(destructiveHint=False), structured_output=True)
    def climate_set(name: str, temperature: float) -> dict[str, Any]:
        """Set a named test climate target."""
        STATE["climate"][name] = temperature
        return {"name": name, "temperature": temperature}

    @server.tool(annotations=ToolAnnotations(destructiveHint=True), structured_output=True)
    def lock_open(name: str) -> dict[str, Any]:
        """Open a named test lock."""
        STATE["locks"][name] = "open"
        return {"name": name, "state": "open"}

    @server.tool(structured_output=True)
    def mystery() -> dict[str, Any]:
        """A tool without safety annotations."""
        return {"mystery": True}

    return server


class BearerMiddleware:
    def __init__(self, app: Any, token: str) -> None:
        self.app = app
        self.expected = f"Bearer {token}".encode("ascii")

    async def __call__(self, scope: dict[str, Any], receive: Any, send: Any) -> None:
        if scope["type"] == "http":
            headers = {name.lower(): value for name, value in scope.get("headers", [])}
            if headers.get(b"authorization") != self.expected:
                await send(
                    {
                        "type": "http.response.start",
                        "status": 401,
                        "headers": [(b"content-type", b"text/plain; charset=utf-8")],
                    }
                )
                await send({"type": "http.response.body", "body": b"unauthorized"})
                return
        await self.app(scope, receive, send)


def main(argv: list[str] | None = None) -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--port", type=int, required=True)
    parser.add_argument("--token")
    args = parser.parse_args(argv)

    import uvicorn

    server = create_server(host="127.0.0.1", port=args.port)
    app: Any = server.streamable_http_app()
    if args.token:
        app = BearerMiddleware(app, args.token)
    uvicorn.run(app, host="127.0.0.1", port=args.port, log_level="warning")


if __name__ == "__main__":
    main()
