from __future__ import annotations

import json

import pytest

from ianest_core.cli import main
from ianest_core.config import load_config
from ianest_core.errors import ConfigError


def test_load_config_missing_file_raises_config_error(tmp_path) -> None:
    config_path = tmp_path / "missing.yaml"

    with pytest.raises(ConfigError) as exc:
        load_config(config_path)

    assert exc.value.type == "ConfigError"
    assert exc.value.field == "config"
    assert str(config_path) in exc.value.message


def test_load_config_invalid_yaml_raises_config_error(tmp_path) -> None:
    config_path = tmp_path / "invalid.yaml"
    config_path.write_text("models: [\n", encoding="utf-8")

    with pytest.raises(ConfigError) as exc:
        load_config(config_path)

    assert exc.value.type == "ConfigError"
    assert exc.value.field == "config"
    assert "invalid YAML" in exc.value.message


def test_cli_emits_clean_config_error_for_missing_file(tmp_path, capsys) -> None:
    config_path = tmp_path / "missing.yaml"

    exit_code = main(["--config", str(config_path), "config", "validate", "--json"])
    captured = capsys.readouterr()

    assert exit_code == 1
    assert captured.out == ""
    assert "Traceback" not in captured.err
    assert json.loads(captured.err)["error"]["type"] == "ConfigError"
