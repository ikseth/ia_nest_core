from __future__ import annotations

import json
import os
import platform
import shutil
import subprocess
from pathlib import Path
from typing import Any, Callable, Iterator

from ianest_core.config import load_config, load_config_data, validate_config_dict
from ianest_core.config.schema import ModelConfig
from ianest_core.evaluation import run_eval as run_eval_core
from ianest_core.errors import CoreError
from ianest_core.provisioning import Provisioner, provisioner_for
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


def pull_models(
    *,
    config_path: str | Path,
    model_references: list[str] | None = None,
    provisioner_factory: Callable[[ModelConfig], Provisioner | None] | None = None,
) -> dict[str, list[str]]:
    config = load_config(config_path)
    models = _selected_models(config.models, model_references or [])
    factory = provisioner_factory or provisioner_for
    pulled: list[str] = []
    present: list[str] = []

    for model in models:
        provisioner = factory(model)
        if provisioner is None:
            raise CoreError(
                "ProvisioningError",
                f"provisioning is not supported for provider '{model.provider}'",
                "provider",
            )
        if model.model_name in provisioner.list_local():
            present.append(model.model_name)
            continue
        provisioner.pull(model.model_name)
        pulled.append(model.model_name)

    return {"pulled": pulled, "present": present}


def _selected_models(models: list[ModelConfig], references: list[str]) -> list[ModelConfig]:
    if not references:
        return models

    selected: list[ModelConfig] = []
    selected_ids: set[str] = set()
    for reference in references:
        matches = [model for model in models if model.id == reference or model.model_name == reference]
        if not matches:
            raise CoreError(
                "ProvisioningError",
                f"modelo no declarado en la config; declaralo primero: '{reference}'",
                "model",
            )
        for model in matches:
            if model.id not in selected_ids:
                selected.append(model)
                selected_ids.add(model.id)
    return selected


def list_domains(*, config_path: str | Path, availability: AvailabilityProvider | None = None) -> dict[str, Any]:
    config = load_config(config_path)
    return {"domains": ModelRegistry(config, availability=availability).domain_records()}


def validate_config(*, config_path: str | Path) -> dict[str, str]:
    validate_config_dict(load_config_data(config_path))
    return {"status": "ok"}


def run_eval(
    *,
    config_path: str | Path,
    battery_dir: str | Path = "eval/battery",
    track: str = "conformance",
) -> dict[str, Any]:
    return run_eval_core(battery_dir=battery_dir, track=track, config_path=config_path)


def health(*, config_path: str | Path, availability: AvailabilityProvider | None = None) -> dict[str, Any]:
    return detect_runtime(config_path=config_path, availability=availability)


def detect_runtime(*, config_path: str | Path, availability: AvailabilityProvider | None = None) -> dict[str, Any]:
    config = load_config(config_path)
    registry = ModelRegistry(config, availability=availability)
    models = registry.model_records()
    return {
        "status": "ok",
        "process": {"ok": True, "pid": os.getpid()},
        "runtime": _runtime_status(),
        "backend": {
            "models": models,
            "available_models": sum(1 for model in models if model["available"]),
            "scope": "configured_models",
        },
        "gpu": _gpu_status(),
        "mcp": {"protocol_version": _mcp_protocol_version()},
    }


def sse_encode(event: dict[str, Any]) -> str:
    event_type = str(event.get("type", "message"))
    return f"event: {event_type}\ndata: {json.dumps(event, ensure_ascii=False, sort_keys=True)}\n\n"


def _gpu_status() -> dict[str, Any]:
    executable = shutil.which("nvidia-smi")
    if executable is None:
        return {"available": False, "detail": "nvidia-smi not found", "gpus": []}
    command = [
        executable,
        "--query-gpu=name,memory.total",
        "--format=csv,noheader,nounits",
    ]
    try:
        completed = subprocess.run(command, check=True, capture_output=True, text=True, timeout=5)
    except (OSError, subprocess.CalledProcessError, subprocess.TimeoutExpired) as exc:
        return {"available": False, "detail": str(exc), "gpus": []}
    gpus = [_parse_gpu_line(line) for line in completed.stdout.splitlines() if line.strip()]
    return {"available": bool(gpus), "detail": "nvidia-smi", "gpus": gpus}


def _runtime_status() -> dict[str, str]:
    return {
        "python": platform.python_version(),
        "platform": platform.platform(),
        "implementation": platform.python_implementation(),
    }


def _parse_gpu_line(line: str) -> dict[str, Any]:
    parts = [part.strip() for part in line.split(",", maxsplit=1)]
    name = parts[0] if parts else ""
    memory_total_mb = None
    if len(parts) > 1:
        try:
            memory_total_mb = int(parts[1])
        except ValueError:
            memory_total_mb = None
    return {"name": name, "memory_total_mb": memory_total_mb}


def _mcp_protocol_version() -> str:
    try:
        from mcp.types import DEFAULT_NEGOTIATED_VERSION
    except ImportError:
        return MCP_PROTOCOL_VERSION_FALLBACK
    return str(DEFAULT_NEGOTIATED_VERSION)
