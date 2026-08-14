from __future__ import annotations

import argparse
import importlib.util
import json
import tomllib
from pathlib import Path
from typing import Any

import pytest

from ianest_core import service
from ianest_core.capabilities import CAPABILITIES
from ianest_core.cli import _build_parser, main


IDENTITY_ARGUMENTS = {"user_id", "service", "session_id", "domain_tag", "namespace"}


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


def test_cli_parser_matches_catalog_in_both_directions() -> None:
    actual = _cli_actions(_build_parser())
    expected: dict[tuple[str, ...], tuple[Any, bool]] = {}
    for capability in CAPABILITIES:
        projection = capability.cli
        if projection is None:
            continue
        key = (projection.group,) if projection.action is None else (projection.group, projection.action)
        expected[key] = (capability, False)
        for alias in projection.aliases:
            expected[(projection.group, alias)] = (capability, True)

    assert set(actual) == set(expected)

    for key, (capability, is_alias) in expected.items():
        parser, summary = actual[key]
        projection = capability.cli
        assert projection is not None

        if not is_alias:
            assert summary == capability.summary
            assert parser.description == projection.description
            assert parser.epilog == projection.epilog

        actions = {
            action.dest: action
            for action in parser._actions
            if not isinstance(action, (argparse._HelpAction, argparse._SubParsersAction))
        }
        expected_arguments = {parameter.name for parameter in capability.params}
        expected_arguments.update(projection.flags)
        if capability.identity:
            expected_arguments.update(IDENTITY_ARGUMENTS)
        assert set(actions) == expected_arguments

        for parameter in capability.params:
            action = actions[parameter.name]
            assert _cli_param_type(action) == parameter.type
            assert action.required is parameter.required
            actual_choices = tuple(action.choices) if action.choices is not None else None
            assert actual_choices == parameter.choices
            assert _cli_default(action) == parameter.default
            assert action.metavar == parameter.metavar
            assert _resolved_help(action) == parameter.summary
            if action.option_strings:
                assert action.option_strings == [f"--{parameter.name.replace('_', '-')}"]
            else:
                assert parameter.type == "array"

        for flag in projection.flags:
            assert actions[flag].option_strings == [f"--{flag}"]


@pytest.mark.skipif(importlib.util.find_spec("mcp") is None, reason="MCP extra not installed")
def test_mcp_tools_match_catalog_in_both_directions() -> None:
    import anyio
    from ianest_core.mcp_server import create_server

    server = create_server("unused")

    async def list_tools():
        return await server.list_tools()

    actual = {tool.name: tool for tool in anyio.run(list_tools)}
    expected = {
        capability.mcp.tool: capability
        for capability in CAPABILITIES
        if capability.mcp is not None
    }

    assert set(actual) == set(expected)

    for tool_name, capability in expected.items():
        schema = actual[tool_name].inputSchema
        properties = schema.get("properties", {})
        required = set(schema.get("required", []))
        expected_names = {parameter.name for parameter in capability.params}
        if capability.identity:
            expected_names.add("identity")

        assert set(properties) == expected_names
        assert required == {
            parameter.name for parameter in capability.params if parameter.required
        }
        for parameter in capability.params:
            assert _mcp_schema_type(properties[parameter.name]) == parameter.type
            if not parameter.required:
                assert properties[parameter.name].get("default") == parameter.default
        if capability.identity:
            assert _mcp_schema_type(properties["identity"]) == "object"
            assert properties["identity"].get("default") is None


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


def _cli_actions(
    parser: argparse.ArgumentParser,
) -> dict[tuple[str, ...], tuple[argparse.ArgumentParser, str]]:
    root_subparsers = next(
        action for action in parser._actions if isinstance(action, argparse._SubParsersAction)
    )
    root_help = {action.dest: action.help for action in root_subparsers._choices_actions}
    result: dict[tuple[str, ...], tuple[argparse.ArgumentParser, str]] = {}
    for group, group_parser in root_subparsers.choices.items():
        action_subparsers = next(
            (
                action
                for action in group_parser._actions
                if isinstance(action, argparse._SubParsersAction)
            ),
            None,
        )
        if action_subparsers is None:
            result[(group,)] = (group_parser, root_help[group])
            continue
        action_help = {action.dest: action.help for action in action_subparsers._choices_actions}
        for action, action_parser in action_subparsers.choices.items():
            result[(group, action)] = (action_parser, action_help[action])
    return result


def _cli_param_type(action: argparse.Action) -> str:
    if isinstance(action, argparse._StoreTrueAction):
        return "boolean"
    if action.nargs == "*":
        return "array"
    return "string"


def _cli_default(action: argparse.Action) -> object | None:
    if action.nargs == "*" and action.default is None:
        return ()
    return action.default


def _resolved_help(action: argparse.Action) -> str:
    help_text = str(action.help)
    if "%(default)s" in help_text:
        return help_text % {"default": action.default}
    return help_text


def _mcp_schema_type(schema: dict[str, Any]) -> str:
    if "type" in schema:
        return str(schema["type"])
    variants = [variant for variant in schema.get("anyOf", []) if variant.get("type") != "null"]
    assert len(variants) == 1
    return str(variants[0]["type"])
