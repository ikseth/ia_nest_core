from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from ianest_core import service
from ianest_core.capabilities import CAPABILITIES
from ianest_core.dotenv import load_dotenv
from ianest_core.errors import CoreError


def create_app(config_path: str | Path = "config/core.yaml"):
    load_dotenv()
    try:
        from starlette.applications import Starlette
        from starlette.requests import Request
        from starlette.responses import JSONResponse, StreamingResponse
        from starlette.routing import Route
    except ImportError as exc:  # pragma: no cover
        raise RuntimeError("REST extra not installed; install ianest-core[interfaces]") from exc

    async def prompt_run(request: Request):
        payload = await request.json()
        return _json(
            service.run_prompt(
                config_path=config_path,
                prompt=payload["prompt"],
                model=payload.get("model"),
                domain=payload.get("domain"),
                identity=payload.get("identity", {}),
            )
        )

    async def prompt_stream(request: Request):
        payload = await request.json()

        def events():
            for event in service.stream_prompt(
                config_path=config_path,
                prompt=payload["prompt"],
                model=payload.get("model"),
                domain=payload.get("domain"),
                identity=payload.get("identity", {}),
            ):
                yield service.sse_encode(event)

        return StreamingResponse(events(), media_type="text/event-stream")

    async def reasoning_run(request: Request):
        payload = await request.json()
        return _json(
            service.run_reasoning(
                config_path=config_path,
                prompt=payload["prompt"],
                model=payload.get("model"),
                domain=payload.get("domain"),
                identity=payload.get("identity", {}),
            )
        )

    async def reasoning_stream(request: Request):
        payload = await request.json()

        def events():
            for event in service.stream_reasoning(
                config_path=config_path,
                prompt=payload["prompt"],
                model=payload.get("model"),
                domain=payload.get("domain"),
                identity=payload.get("identity", {}),
            ):
                yield service.sse_encode(event)

        return StreamingResponse(events(), media_type="text/event-stream")

    async def task_run(request: Request):
        payload = await request.json()
        return _json(
            service.run_task(
                config_path=config_path,
                prompt=payload["prompt"],
                mode=payload.get("mode", "pipeline"),
                effort=payload.get("effort"),
                identity=payload.get("identity", {}),
            )
        )

    async def task_stream(request: Request):
        payload = await request.json()

        def events():
            for event in service.stream_task(
                config_path=config_path,
                prompt=payload["prompt"],
                mode=payload.get("mode", "pipeline"),
                effort=payload.get("effort"),
                identity=payload.get("identity", {}),
            ):
                yield service.sse_encode(event)

        return StreamingResponse(events(), media_type="text/event-stream")

    async def domain_route(request: Request):
        payload = await request.json()
        return _json(
            service.route_domain(
                config_path=config_path,
                prompt=payload["prompt"],
                identity=payload.get("identity", {}),
            )
        )

    async def model_list(request: Request):
        return _json(service.list_models(config_path=config_path))

    async def domain_list(request: Request):
        return _json(service.list_domains(config_path=config_path))

    async def config_validate(request: Request):
        return _json(service.validate_config(config_path=config_path))

    async def eval_run(request: Request):
        payload = await request.json()
        return _json(
            service.run_eval(
                config_path=config_path,
                battery_dir=payload.get("battery_dir", "eval/battery"),
                track=payload.get("track", "conformance"),
            )
        )

    async def runtime_health(request: Request):
        return _json(service.health(config_path=config_path))

    async def capability_list(request: Request):
        return _json(service.list_capabilities())

    async def core_error_handler(request: Request, exc: CoreError):
        return JSONResponse({"error": exc.to_dict()}, status_code=400)

    handlers = {
        "capability.list": capability_list,
        "config.validate": config_validate,
        "domain.list": domain_list,
        "domain.route": domain_route,
        "eval.run": eval_run,
        "model.list": model_list,
        "prompt.run": prompt_run,
        "prompt.stream": prompt_stream,
        "reasoning.run": reasoning_run,
        "reasoning.stream": reasoning_stream,
        "runtime.health": runtime_health,
        "task.run": task_run,
        "task.stream": task_stream,
    }
    routes = [
        Route(capability.rest.path, handlers[capability.name], methods=[capability.rest.method])
        for capability in CAPABILITIES
        if capability.rest is not None
    ]
    return Starlette(routes=routes, exception_handlers={CoreError: core_error_handler})


def _json(payload: dict[str, Any]):
    from starlette.responses import JSONResponse

    return JSONResponse(payload)
