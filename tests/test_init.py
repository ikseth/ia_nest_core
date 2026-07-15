from __future__ import annotations

import os
from pathlib import Path

from ianest_core.cli import main


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
