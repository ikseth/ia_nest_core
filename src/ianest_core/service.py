from __future__ import annotations

import json
import os
import platform
from pathlib import Path
from typing import Any, Iterator

import yaml

from ianest_core.config import load_config, validate_config_dict
from ianest_core.evaluation import run_eval as run_eval_core
from ianest_core.registry import AvailabilityProvider, ModelRegistry
from ianest_core.runtime import DomainRuntime, PromptRuntime, ReasoningRuntime

MCP_PROTOCOL_VERSION_FALLBACK = "2025-03-26"


def run_prompt(
    *,
    config_path: str | Path,
    prompt: str,
    model: str | None = None,
    domain: str | None = None,
    identity: dict[str, str] | None = None,
    availability: AvailabilityProvider | None = None,
) -> dict[str, Any]:
    config = load_config(config_path)
    result = PromptRuntime(config, availability=availability).run(
        prompt=prompt,
        model_id=model,
        domain_id=domain,
        identity_override=identity or {},
    )
    return result.to_dict()


def stream_prompt(
    *,
    config_path: str | Path,
    prompt: str,
    model: str | None = None,
    domain: str | None = None,
    identity: dict[str, str] | None = None,
    availability: AvailabilityProvider | None = None,
) -> Iterator[dict[str, Any]]:
    config = load_config(config_path)
    runtime = PromptRuntime(config, availability=availability)
    for event in runtime.stream(
        prompt=prompt,
        model_id=model,
        domain_id=domain,
        identity_override=identity or {},
    ):
        yield {"type": event.type, "data": event.data}


def run_reasoning(
    *,
    config_path: str | Path,
    prompt: str,
    model: str | None = None,
    domain: str | None = None,
    identity: dict[str, str] | None = None,
    availability: AvailabilityProvider | None = None,
) -> dict[str, Any]:
    config = load_config(config_path)
    result = ReasoningRuntime(config, availability=availability).run(
        prompt=prompt,
        model_id=model,
        domain_id=domain,
        identity_override=identity or {},
    )
    return result.to_dict()


def stream_reasoning(
    *,
    config_path: str | Path,
    prompt: str,
    model: str | None = None,
    domain: str | None = None,
    identity: dict[str, str] | None = None,
    availability: AvailabilityProvider | None = None,
) -> Iterator[dict[str, Any]]:
    config = load_config(config_path)
    runtime = ReasoningRuntime(config, availability=availability)
    for event in runtime.stream(
        prompt=prompt,
        model_id=model,
        domain_id=domain,
        identity_override=identity or {},
    ):
        yield {"type": event.type, "data": event.data}


def route_domain(
    *,
    config_path: str | Path,
    prompt: str,
    tags: list[str] | None = None,
    identity: dict[str, str] | None = None,
    availability: AvailabilityProvider | None = None,
) -> dict[str, Any]:
    config = load_config(config_path)
    result = DomainRuntime(config, availability=availability).route(
        prompt=prompt,
        tags=tags or [],
        identity_override=identity or {},
    )
    return result.to_dict()


def list_models(*, config_path: str | Path, availability: AvailabilityProvider | None = None) -> dict[str, Any]:
    config = load_config(config_path)
    return {"models": ModelRegistry(config, availability=availability).model_records()}


def list_domains(*, config_path: str | Path, availability: AvailabilityProvider | None = None) -> dict[str, Any]:
    config = load_config(config_path)
    return {"domains": ModelRegistry(config, availability=availability).domain_records()}


def validate_config(*, config_path: str | Path) -> dict[str, str]:
    with Path(config_path).open("r", encoding="utf-8") as handle:
        raw = yaml.safe_load(handle) or {}
    validate_config_dict(raw)
    return {"status": "ok"}


def run_eval(
    *,
    config_path: str | Path,
    battery_dir: str | Path = "eval/battery",
    track: str = "conformance",
) -> dict[str, Any]:
    return run_eval_core(battery_dir=battery_dir, track=track, config_path=config_path)


def health(*, config_path: str | Path, availability: AvailabilityProvider | None = None) -> dict[str, Any]:
    config = load_config(config_path)
    registry = ModelRegistry(config, availability=availability)
    models = registry.model_records()
    return {
        "status": "ok",
        "process": {"ok": True, "pid": os.getpid(), "python": platform.python_version()},
        "backend": {
            "models": models,
            "available_models": sum(1 for model in models if model["available"]),
        },
        "gpu": _gpu_status(),
        "mcp": {"protocol_version": _mcp_protocol_version()},
    }


def sse_encode(event: dict[str, Any]) -> str:
    event_type = str(event.get("type", "message"))
    return f"event: {event_type}\ndata: {json.dumps(event, ensure_ascii=False, sort_keys=True)}\n\n"


def _gpu_status() -> dict[str, Any]:
    dev_path = Path("/dev/nvidia0")
    return {"available": dev_path.exists(), "detail": "local best_effort"}


def _mcp_protocol_version() -> str:
    try:
        from mcp.types import DEFAULT_NEGOTIATED_VERSION
    except ImportError:
        return MCP_PROTOCOL_VERSION_FALLBACK
    return str(DEFAULT_NEGOTIATED_VERSION)
