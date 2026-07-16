from __future__ import annotations

import argparse
from pathlib import Path
from typing import Any

from ianest_core import service
from ianest_core.dotenv import load_dotenv


def create_server(
    config_path: str | Path = "config/core.yaml",
    *,
    host: str = "127.0.0.1",
    port: int = 8090,
):
    load_dotenv()
    try:
        from mcp.server.fastmcp import FastMCP
    except ImportError as exc:  # pragma: no cover
        raise RuntimeError("MCP extra not installed; install ianest-core[interfaces]") from exc

    server = FastMCP("ia_nest_core", host=host, port=port)

    @server.tool(name="prompt.run", structured_output=True)
    def prompt_run(prompt: str, model: str | None = None, domain: str | None = None, identity: dict[str, str] | None = None) -> dict[str, Any]:
        return service.run_prompt(
            config_path=config_path,
            prompt=prompt,
            model=model,
            domain=domain,
            identity=identity or {},
        )

    @server.tool(name="reasoning.run", structured_output=True)
    def reasoning_run(prompt: str, model: str | None = None, domain: str | None = None, identity: dict[str, str] | None = None) -> dict[str, Any]:
        return service.run_reasoning(
            config_path=config_path,
            prompt=prompt,
            model=model,
            domain=domain,
            identity=identity or {},
        )

    @server.tool(name="task.run", structured_output=True)
    def task_run(prompt: str, identity: dict[str, str] | None = None) -> dict[str, Any]:
        return service.run_task(config_path=config_path, prompt=prompt, identity=identity or {})

    @server.tool(name="domain.route", structured_output=True)
    def domain_route(prompt: str, tags: list[str] | None = None, identity: dict[str, str] | None = None) -> dict[str, Any]:
        return service.route_domain(
            config_path=config_path,
            prompt=prompt,
            tags=tags or [],
            identity=identity or {},
        )

    @server.tool(name="model.list", structured_output=True)
    def model_list() -> dict[str, Any]:
        return service.list_models(config_path=config_path)

    @server.tool(name="domain.list", structured_output=True)
    def domain_list() -> dict[str, Any]:
        return service.list_domains(config_path=config_path)

    @server.tool(name="config.validate", structured_output=True)
    def config_validate() -> dict[str, str]:
        return service.validate_config(config_path=config_path)

    @server.tool(name="eval.run", structured_output=True)
    def eval_run(track: str = "conformance", battery_dir: str = "eval/battery") -> dict[str, Any]:
        return service.run_eval(config_path=config_path, track=track, battery_dir=battery_dir)

    @server.tool(name="runtime.health", structured_output=True)
    def runtime_health() -> dict[str, Any]:
        return service.health(config_path=config_path)

    return server


def main(argv: list[str] | None = None) -> None:
    parser = argparse.ArgumentParser(prog="ianest-mcp")
    parser.add_argument("--config", default="config/core.yaml", help="ruta de configuracion YAML")
    parser.add_argument("--transport", choices=["stdio", "sse"], default="stdio")
    parser.add_argument("--host", default="127.0.0.1")
    parser.add_argument("--port", type=int, default=8090)
    args = parser.parse_args(argv)

    create_server(args.config, host=args.host, port=args.port).run(transport=args.transport)


if __name__ == "__main__":
    main()
