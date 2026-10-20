from __future__ import annotations

import argparse
import importlib.util
import json
import re
import shutil
import subprocess
import sys
import tomllib
from dataclasses import replace
from pathlib import Path
from typing import Any

import pytest

from ianest_core import service
from ianest_core import build_identity
from ianest_core.capabilities import CAPABILITIES, _assert_catalog_invariants
from ianest_core.cli import _build_parser, main


IDENTITY_ARGUMENTS = {"user_id", "service", "session_id", "domain_tag", "namespace"}
BUILD_ID_PATTERN = re.compile(r"^(?:[0-9a-f]{64}|unknown)$")

_PRESENTATION_INVOCATIONS = {
    "capability.list": ("list_capabilities", ["capability", "list"]),
    "domain.list": ("list_domains", ["--config", "unused", "domain", "list"]),
    "domain.route": (
        "route_domain",
        ["--config", "unused", "domain", "route", "--prompt", "hola"],
    ),
    "eval.run": ("run_eval", ["--config", "unused", "eval", "run"]),
    "model.list": ("list_models", ["--config", "unused", "model", "list"]),
    "prompt.run": (
        "run_prompt",
        ["--config", "unused", "prompt", "run", "--prompt", "hola"],
    ),
    "reasoning.run": (
        "run_reasoning",
        ["--config", "unused", "reasoning", "run", "--prompt", "hola"],
    ),
    "task.plan": (
        "plan_task",
        ["--config", "unused", "task", "plan", "--prompt", "hola"],
    ),
    "task.run": (
        "stream_task",
        ["--config", "unused", "task", "run", "--prompt", "hola"],
    ),
}


def test_capability_list_core_version_matches_pyproject() -> None:
    pyproject = Path(__file__).resolve().parents[1] / "pyproject.toml"
    declared = tomllib.loads(pyproject.read_text(encoding="utf-8"))["project"]["version"]

    assert service.list_capabilities()["core_version"] == declared


def test_build_id_shape_and_stability_within_process() -> None:
    first_catalog = service.list_capabilities()["build_id"]
    second_catalog = service.list_capabilities()["build_id"]
    first_health = service.health(
        config_path="eval/fixtures/config.yaml",
        gpu_status_factory=lambda: {"available": False, "gpus": []},
    )["build_id"]
    second_health = service.health(
        config_path="eval/fixtures/config.yaml",
        gpu_status_factory=lambda: {"available": False, "gpus": []},
    )["build_id"]

    values = [first_catalog, second_catalog, first_health, second_health]
    assert all(BUILD_ID_PATTERN.fullmatch(value) for value in values)
    assert len(set(values)) == 1


def test_build_id_is_unknown_when_package_digest_cannot_be_read(monkeypatch) -> None:
    original = Path.read_bytes

    def fail_for_package_python(path: Path) -> bytes:
        if path.suffix == ".py" and "ianest_core" in path.parts:
            raise OSError("scripted unreadable package")
        return original(path)

    monkeypatch.setattr(Path, "read_bytes", fail_for_package_python)

    assert build_identity._calculate_build_id() == "unknown"


def test_build_id_identifies_the_package_loaded_at_service_import(tmp_path) -> None:
    source_package = Path(service.__file__).resolve().parent
    copied_package = tmp_path / "ianest_core"
    shutil.copytree(source_package, copied_package)
    before = _package_digest(copied_package)

    script = f"""
import json
import sys
from pathlib import Path

sys.path.insert(0, {str(tmp_path)!r})
from ianest_core import service

(Path({str(copied_package)!r}) / "written_after_import.py").write_text("VALUE = 1\\n", encoding="utf-8")
print(json.dumps(service.list_capabilities()["build_id"]))
"""
    observed = json.loads(subprocess.check_output([sys.executable, "-c", script], text=True))
    after = _package_digest(copied_package)

    assert observed == before
    assert observed != after


def test_catalog_cli_projections_declare_valid_presentation_forms() -> None:
    entries = service.list_capabilities()["capabilities"]

    for entry in entries:
        projection = entry["cli"]
        if projection is None:
            continue
        presentation = projection["presentation"]
        form = presentation["form"]
        assert form in {"text", "row", "table", "opaque"}
        if form == "text":
            assert set(presentation) == {"form", "field"}
        elif form == "row":
            assert set(presentation) == {"form", "fields"}
        elif form == "table":
            assert set(presentation) == {"form", "items", "columns"}
        else:
            assert set(presentation) == {"form"}


def test_catalog_gate_rejects_missing_cli_presentation() -> None:
    prompt_run = next(capability for capability in CAPABILITIES if capability.name == "prompt.run")
    broken = replace(prompt_run, cli=replace(prompt_run.cli, presentation=None))
    catalog = tuple(broken if capability.name == broken.name else capability for capability in CAPABILITIES)

    with pytest.raises(AssertionError):
        _assert_catalog_invariants(catalog)


@pytest.mark.parametrize(
    "capability",
    [
        capability
        for capability in CAPABILITIES
        if capability.cli is not None and capability.cli.presentation["form"] != "opaque"
    ],
    ids=lambda capability: capability.name,
)
def test_catalog_presentation_matches_what_the_renderer_prints(
    capability, monkeypatch, capsys
) -> None:
    projection = capability.cli
    assert projection is not None
    payload = _presentation_payload(capability.name, projection.presentation)
    service_name, argv = _PRESENTATION_INVOCATIONS[capability.name]
    if capability.name == "task.run":
        events = iter(({"type": "task_done", "data": payload},))
        monkeypatch.setattr(service, service_name, lambda **kwargs: events)
    else:
        monkeypatch.setattr(service, service_name, lambda **kwargs: payload)

    assert main(argv) == 0
    rendered = capsys.readouterr().out.strip()

    assert rendered == _expected_presentation(payload, projection.presentation)


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
        expected_arguments = {
            parameter.name
            for parameter in capability.params
            if parameter.cli
        }
        expected_arguments.update(input.name.replace("-", "_") for input in projection.inputs)
        expected_arguments.update(projection.flags)
        if capability.identity:
            expected_arguments.update(IDENTITY_ARGUMENTS)
        assert set(actions) == expected_arguments

        for parameter in capability.params:
            if not parameter.cli:
                continue
            action = actions[parameter.name]
            assert _cli_param_type(action) == parameter.type
            assert action.required is parameter.required
            actual_choices = tuple(action.choices) if action.choices is not None else None
            assert actual_choices == parameter.choices
            if any(parameter.name in input.targets for input in projection.inputs):
                assert action.default == argparse.SUPPRESS
            else:
                assert _cli_default(action) == parameter.default
            assert action.metavar == parameter.metavar
            assert _resolved_help(action) == parameter.summary
            if action.option_strings:
                assert action.option_strings == [f"--{parameter.name.replace('_', '-')}"]
            else:
                assert parameter.type == "array"

        for input in projection.inputs:
            action = actions[input.name.replace("-", "_")]
            assert action.option_strings == [f"--{input.name}"]
            assert action.metavar == input.metavar
            assert _resolved_help(action) == input.summary

        for flag in projection.flags:
            assert actions[flag].option_strings == [f"--{flag}"]


def test_catalog_rejects_cli_disabled_parameter_without_input_target() -> None:
    task_run = next(capability for capability in CAPABILITIES if capability.name == "task.run")
    plan = next(parameter for parameter in task_run.params if parameter.name == "plan")
    assert plan.cli is False
    broken = replace(task_run, cli=replace(task_run.cli, inputs=()))
    catalog = tuple(broken if capability.name == broken.name else capability for capability in CAPABILITIES)

    with pytest.raises(AssertionError):
        _assert_catalog_invariants(catalog)


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


def _presentation_payload(name: str, presentation: dict[str, object]) -> dict[str, Any]:
    def sentinel(field: object) -> str:
        return f"SENTINEL_{name}_{field}".upper().replace(".", "_")

    form = presentation["form"]
    if form == "text":
        payload = {str(presentation["field"]): sentinel(presentation["field"])}
    elif form == "row":
        fields = presentation["fields"]
        assert isinstance(fields, (list, tuple))
        payload = {str(field): sentinel(field) for field in fields}
    else:
        assert form == "table"
        columns = presentation["columns"]
        assert isinstance(columns, (list, tuple))
        payload = {
            str(presentation["items"]): [
                {
                    **{str(column): sentinel(column) for column in columns},
                    "not_declared": sentinel("item_not_declared"),
                }
            ]
        }
    payload["not_declared"] = sentinel("not_declared")
    if name == "task.run":
        payload.update({"stop_reason": "task_done", "degradations": []})
    return payload


def _expected_presentation(
    payload: dict[str, Any], presentation: dict[str, object]
) -> str:
    form = presentation["form"]
    if form == "text":
        return str(payload[str(presentation["field"])])
    if form == "row":
        fields = presentation["fields"]
        assert isinstance(fields, (list, tuple))
        return "\t".join(str(payload[str(field)]) for field in fields)
    assert form == "table"
    columns = presentation["columns"]
    assert isinstance(columns, (list, tuple))
    items = payload[str(presentation["items"])]
    assert isinstance(items, list)
    return "\n".join(
        "\t".join(str(item[str(column)]) for column in columns)
        for item in items
    )


def _package_digest(package_root: Path) -> str:
    import hashlib

    digest = hashlib.sha256()
    paths = sorted(
        (
            path
            for path in package_root.rglob("*.py")
            if "__pycache__" not in path.relative_to(package_root).parts
        ),
        key=lambda path: path.relative_to(package_root).as_posix(),
    )
    for path in paths:
        digest.update(path.relative_to(package_root).as_posix().encode("utf-8"))
        digest.update(b"\0")
        digest.update(path.read_bytes())
        digest.update(b"\0")
    return digest.hexdigest()
