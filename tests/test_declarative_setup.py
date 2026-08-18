from __future__ import annotations

import subprocess
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[1]
SETUP = REPO_ROOT / "deploy" / "setup.sh"


def run_print_config(*args: str) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        ["bash", str(SETUP), *args, "--print-config"],
        cwd=REPO_ROOT,
        capture_output=True,
        text=True,
    )


def test_print_config_uses_file_then_argument_then_default(tmp_path: Path) -> None:
    config = tmp_path / "setup.conf"
    config.write_text("REST_PORT=18000\n", encoding="ascii")

    from_file = run_print_config("--config", str(config))
    overridden = run_print_config("--config", str(config), "--rest-port", "18001")
    defaults = run_print_config()

    assert from_file.returncode == 0, from_file.stderr
    assert "REST_PORT=18000 (file)" in from_file.stdout
    assert overridden.returncode == 0, overridden.stderr
    assert "REST_PORT=18001 (argument)" in overridden.stdout
    assert defaults.returncode == 0, defaults.stderr
    assert "REST_PORT=8000 (default)" in defaults.stdout


def test_print_config_rejects_unknown_key(tmp_path: Path) -> None:
    config = tmp_path / "core.yaml"
    config.write_text("UNKNOWN=value\n", encoding="ascii")

    result = run_print_config("--config", str(config))

    assert result.returncode != 0
    assert "clave desconocida" in result.stderr
    assert "ejemplo.setup.conf" in result.stderr


def test_print_config_rejects_enabled_service_without_install(tmp_path: Path) -> None:
    config = tmp_path / "setup.conf"
    config.write_text("SERVICE_INSTALL=false\nSERVICE_ENABLE=true\n", encoding="ascii")

    result = run_print_config("--config", str(config))

    assert result.returncode != 0
    assert "SERVICE_ENABLE=true requiere SERVICE_INSTALL=true" in result.stderr
