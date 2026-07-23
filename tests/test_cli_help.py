from __future__ import annotations

import pytest

from ianest_core import cli


GROUPS = ["prompt", "reasoning", "task", "domain", "model", "config", "eval", "runtime"]
ACTIONS = [
    ("init",),
    ("prompt", "run"),
    ("reasoning", "run"),
    ("reasoning", "stream"),
    ("task", "run"),
    ("domain", "route"),
    ("domain", "list"),
    ("model", "list"),
    ("model", "pull"),
    ("config", "validate"),
    ("eval", "run"),
    ("runtime", "health"),
    ("runtime", "detect"),
]
QUIET_ACTIONS = [
    ("prompt", "run"),
    ("reasoning", "run"),
    ("reasoning", "stream"),
    ("task", "run"),
]


def _help(argv: list[str], capsys: pytest.CaptureFixture[str]) -> str:
    with pytest.raises(SystemExit) as exc_info:
        cli.main([*argv, "--help"])
    assert exc_info.value.code == 0
    return capsys.readouterr().out


def test_root_help_is_a_descriptive_index(capsys: pytest.CaptureFixture[str]) -> None:
    output = _help([], capsys)
    assert "Orquesta modelos locales" in output
    assert "ianest GRUPO ACCION --help" in output
    for group in ["init", *GROUPS]:
        assert group in output


@pytest.mark.parametrize("group", GROUPS)
def test_group_help_describes_its_actions(group: str, capsys: pytest.CaptureFixture[str]) -> None:
    output = _help([group], capsys)
    assert "acciones:" in output
    assert "ACCION" in output


@pytest.mark.parametrize("action", ACTIONS)
def test_action_help_describes_every_argument(
    action: tuple[str, ...], capsys: pytest.CaptureFixture[str]
) -> None:
    output = _help(list(action), capsys)
    assert "usage: ianest" in output
    assert "--help" in output
    for line in output.splitlines():
        if line.lstrip().startswith("--"):
            assert len(line.split(maxsplit=1)) == 2, line


def test_prompt_help_explains_model_precedence(capsys: pytest.CaptureFixture[str]) -> None:
    output = _help(["prompt", "run"], capsys)
    normalized = " ".join(output.split())
    assert "--model tiene prioridad sobre --domain" in normalized
    assert "router selecciona el dominio y el modelo" in normalized


def test_task_run_help_explains_execution_modes(capsys: pytest.CaptureFixture[str]) -> None:
    output = _help(["task", "run"], capsys)
    normalized = " ".join(output.split())
    assert "--mode {pipeline,coverage}" in normalized
    assert "por defecto: pipeline" in normalized
    assert "unidades enumerables" in normalized


@pytest.mark.parametrize("action", QUIET_ACTIONS)
def test_run_and_stream_help_include_quiet(
    action: tuple[str, ...], capsys: pytest.CaptureFixture[str]
) -> None:
    assert "--quiet" in _help(list(action), capsys)


def test_help_does_not_load_environment(monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]) -> None:
    def fail_if_called(*args: object, **kwargs: object) -> None:
        raise AssertionError("load_dotenv must not run while rendering help")

    monkeypatch.setattr(cli, "load_dotenv", fail_if_called)
    _help(["runtime", "health"], capsys)
