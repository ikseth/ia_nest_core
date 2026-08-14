from __future__ import annotations

import importlib.util
import json
import tomllib
from pathlib import Path

import pytest

from ianest_core import service
from ianest_core.capabilities import CAPABILITIES
from ianest_core.cli import main


def test_capability_list_core_version_matches_pyproject() -> None:
    pyproject = Path(__file__).resolve().parents[1] / "pyproject.toml"
    declared = tomllib.loads(pyproject.read_text(encoding="utf-8"))["project"]["version"]

    assert service.list_capabilities()["core_version"] == declared


@pytest.mark.skipif(importlib.util.find_spec("starlette") is None, reason="REST extra not installed")
def test_rest_route_table_matches_catalog() -> None:
    from ianest_core.rest import create_app

    actual = {
        (route.path, method)
        for route in create_app("unused").routes
        for method in route.methods
        if method != "HEAD"
    }
    expected = {
        (capability.rest.path, capability.rest.method)
        for capability in CAPABILITIES
        if capability.rest is not None
    }

    assert actual == expected


def test_runtime_health_and_capability_list_declare_same_core_version(monkeypatch) -> None:
    monkeypatch.setattr(service, "load_config", lambda path: object())
    monkeypatch.setattr(service, "ModelRegistry", _Registry)
    monkeypatch.setattr(service, "_gpu_status", lambda: {"available": False, "gpus": []})

    assert service.health(config_path="unused")["core_version"] == service.list_capabilities()["core_version"]


def test_capability_list_cli_json_matches_service(capsys) -> None:
    expected = json.loads(json.dumps(service.list_capabilities()))

    assert main(["capability", "list", "--json"]) == 0

    assert json.loads(capsys.readouterr().out) == expected


@pytest.mark.skipif(importlib.util.find_spec("mcp") is None, reason="MCP extra not installed")
def test_capability_list_mcp_matches_service() -> None:
    import anyio
    from ianest_core.mcp_server import create_server

    server = create_server("unused")

    async def call_capability_list():
        return await server.call_tool("capability.list", {})

    _, structured = anyio.run(call_capability_list)
    expected = json.loads(json.dumps(service.list_capabilities()))
    assert structured == expected


class _Registry:
    def __init__(self, config, availability=None):
        pass

    def model_records(self):
        return []
