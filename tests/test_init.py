from __future__ import annotations

import os
from pathlib import Path

import pytest

from ianest_core import service
from ianest_core.cli import main
from ianest_core.config import load_config
from ianest_core.config.schema import CoverageConfig, OrchestrationConfig
from ianest_core.runtime import TaskRuntime


REPO_ROOT = Path(__file__).resolve().parents[1]


def test_init_creates_minimal_config_and_env(tmp_path, monkeypatch, capsys) -> None:
    monkeypatch.chdir(tmp_path)
    monkeypatch.delenv("OPENAI_COMPAT_BASE_URL", raising=False)

    exit_code = main(["init", "--endpoint", "http://example.test/v1"])
    captured = capsys.readouterr()

    assert exit_code == 0
    assert (tmp_path / "config/core.yaml").read_text(encoding="utf-8") == (
        REPO_ROOT / "config/core.example.yaml"
    ).read_text(encoding="utf-8")
    assert (tmp_path / ".env").read_text(encoding="utf-8") == "OPENAI_COMPAT_BASE_URL=http://example.test/v1\n"
    assert captured.out.splitlines() == ["created config/core.yaml", "created .env", "ok"]


def test_init_keeps_existing_files_without_force(tmp_path, monkeypatch, capsys) -> None:
    monkeypatch.chdir(tmp_path)
    config_path = tmp_path / "config/core.yaml"
    config_path.parent.mkdir()
    config_path.write_text("existing config\n", encoding="utf-8")
    env_path = tmp_path / ".env"
    env_path.write_text("EXISTING=value\n", encoding="utf-8")

    exit_code = main(["init", "--endpoint", "http://example.test/v1"])
    captured = capsys.readouterr()

    assert exit_code == 1
    assert config_path.read_text(encoding="utf-8") == "existing config\n"
    assert env_path.read_text(encoding="utf-8") == "EXISTING=value\n"
    assert "use --force" in captured.err


def test_init_force_overwrites_and_validates_lab_template(tmp_path, monkeypatch, capsys) -> None:
    monkeypatch.chdir(tmp_path)
    monkeypatch.setenv("OPENAI_COMPAT_BASE_URL", "")
    config_path = tmp_path / "config/core.yaml"
    config_path.parent.mkdir()
    config_path.write_text("existing config\n", encoding="utf-8")
    (tmp_path / ".env").write_text("EXISTING=value\n", encoding="utf-8")

    exit_code = main(
        ["init", "--template", "lab", "--endpoint", "http://example.test/v1", "--force"]
    )
    captured = capsys.readouterr()

    assert exit_code == 0
    assert config_path.read_text(encoding="utf-8") == (
        REPO_ROOT / "config/core.lab.example.yaml"
    ).read_text(encoding="utf-8")
    assert (tmp_path / ".env").read_text(encoding="utf-8") == "OPENAI_COMPAT_BASE_URL=http://example.test/v1\n"
    assert os.environ["OPENAI_COMPAT_BASE_URL"] == "http://example.test/v1"
    assert captured.out.endswith("ok\n")


@pytest.mark.parametrize("template", ["minimal", "lab"])
def test_init_templates_declare_orchestration_and_allow_task_run(tmp_path, monkeypatch, capsys, template) -> None:
    monkeypatch.chdir(tmp_path)

    assert main(["init", "--template", template, "--endpoint", "http://example.test/v1"]) == 0
    capsys.readouterr()
    config_path = tmp_path / "config/core.yaml"
    config = load_config(config_path)
    orchestration = config.orchestration
    assert orchestration is not None
    for field in ("max_subtasks", "max_iterations", "max_replans", "max_time_s", "max_context_tokens", "max_parallel"):
        assert getattr(orchestration, field) == OrchestrationConfig.__dataclass_fields__[field].default
    assert orchestration.coverage is not None
    for field in (
        "units_per_chunk",
        "max_chunks",
        "max_total_tokens",
        "max_retries_per_unit",
        "max_no_progress_iterations",
    ):
        assert getattr(orchestration.coverage, field) == CoverageConfig.__dataclass_fields__[field].default

    def stream_task_without_backend(*, config_path, **kwargs):
        TaskRuntime(load_config(config_path))
        return iter(())

    monkeypatch.setattr(service, "stream_task", stream_task_without_backend)
    assert main(["--config", str(config_path), "task", "run", "--prompt", "tarea"]) == 0
    assert capsys.readouterr().err == ""
