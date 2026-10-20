from __future__ import annotations

import os
import subprocess
import sys
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


def test_print_config_models_uses_file_then_argument_then_default(tmp_path: Path) -> None:
    config = tmp_path / "setup.conf"
    config.write_text("MODELS=skip\n", encoding="ascii")

    from_file = run_print_config("--config", str(config))
    overridden = run_print_config("--config", str(config), "--models", "pull")
    defaults = run_print_config()

    assert from_file.returncode == 0, from_file.stderr
    assert "MODELS=skip (file)" in from_file.stdout
    assert overridden.returncode == 0, overridden.stderr
    assert "MODELS=pull (argument)" in overridden.stdout
    assert defaults.returncode == 0, defaults.stderr
    assert "MODELS=pull (default)" in defaults.stdout


def test_print_config_rejects_invalid_models_value(tmp_path: Path) -> None:
    config = tmp_path / "setup.conf"
    config.write_text("MODELS=download\n", encoding="ascii")

    result = run_print_config("--config", str(config))

    assert result.returncode != 0
    assert "MODELS debe ser pull o skip" in result.stderr


def run_isolated_setup(
    tmp_path: Path, models: str, prompt_status: int = 0
) -> tuple[subprocess.CompletedProcess[str], str]:
    """Run setup through its model and verification stages without a host install."""
    repo = tmp_path / "repo"
    deploy_dir = repo / "deploy"
    config_dir = repo / "config"
    venv_bin = repo / ".venv" / "bin"
    install_root = tmp_path / "install-root"
    deploy_dir.mkdir(parents=True)
    config_dir.mkdir()
    venv_bin.mkdir(parents=True)

    setup_source = SETUP.read_text(encoding="ascii")
    setup_source = setup_source.replace(
        'readonly INSTALL_ROOT="/opt/ia_nest"',
        f'readonly INSTALL_ROOT="{install_root}"',
    )
    assert 'readonly INSTALL_ROOT="/opt/ia_nest"' not in setup_source
    setup = deploy_dir / "setup.sh"
    setup.write_text(setup_source, encoding="ascii")
    setup.chmod(0o755)
    (config_dir / "core.lab.example.yaml").write_text("models: []\n", encoding="ascii")
    (repo / "install.sh").write_text(
        "#!/usr/bin/env bash\nset -euo pipefail\nprintf 'install %s\\n' \"$*\" >> \"$IANEST_SETUP_LOG\"\n",
        encoding="ascii",
    )
    (venv_bin / "python").symlink_to(Path(sys.executable))
    (venv_bin / "ianest").write_text(
        "#!/usr/bin/env bash\n"
        "set -euo pipefail\n"
        "printf '%s\\n' \"$*\" >> \"$IANEST_SETUP_LOG\"\n"
        "if [[ \"$*\" == *\"prompt run\"* ]]; then\n"
        "  exit \"${IANEST_PROMPT_STATUS:-0}\"\n"
        "fi\n"
        "exit 0\n",
        encoding="ascii",
    )
    (venv_bin / "ianest").chmod(0o755)

    config = tmp_path / "setup.conf"
    config.write_text(
        f"PROVISION_BACKEND=false\nSERVICE_INSTALL=false\nMODELS={models}\nVERIFY=strict\n",
        encoding="ascii",
    )
    log = tmp_path / "ianest.log"
    env = os.environ | {
        "IANEST_SETUP_LOG": str(log),
        "IANEST_PROMPT_STATUS": str(prompt_status),
    }
    result = subprocess.run(
        ["bash", str(setup), "--config", str(config)],
        cwd=repo,
        capture_output=True,
        text=True,
        env=env,
    )
    return result, log.read_text(encoding="ascii")


def test_setup_models_skip_omits_pull_and_strict_still_verifies(tmp_path: Path) -> None:
    result, log = run_isolated_setup(tmp_path / "success", "skip")

    assert result.returncode == 0, result.stderr
    assert "MODELS=skip: el operador afirma que el backend ya tiene los modelos" in result.stdout
    assert "model pull" not in log
    assert "prompt run" in log

    failed, failed_log = run_isolated_setup(tmp_path / "strict-failure", "skip", prompt_status=1)

    assert failed.returncode != 0
    assert "verificacion fallida" in failed.stderr
    assert "model pull" not in failed_log
    assert "prompt run" in failed_log


def test_setup_models_pull_invokes_pull(tmp_path: Path) -> None:
    result, log = run_isolated_setup(tmp_path, "pull")

    assert result.returncode == 0, result.stderr
    assert "model pull" in log
    assert "prompt run" in log
