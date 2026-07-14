from __future__ import annotations

import os
import subprocess
from pathlib import Path

from ianest_core.dotenv import load_dotenv
from ianest_core import mcp_server


def test_dotenv_helper_loads_without_overwriting(tmp_path, monkeypatch) -> None:
    env_path = tmp_path / ".env"
    env_path.write_text(
        "\n# comentario\nOPENAI_COMPAT_BASE_URL=fake://dotenv\nEXISTING=value-from-file\nQUOTED=\"valor citado\"\n",
        encoding="utf-8",
    )
    monkeypatch.delenv("OPENAI_COMPAT_BASE_URL", raising=False)
    monkeypatch.setenv("EXISTING", "value-from-env")

    load_dotenv(env_path)

    assert os.environ["OPENAI_COMPAT_BASE_URL"] == "fake://dotenv"
    assert os.environ["EXISTING"] == "value-from-env"
    assert os.environ["QUOTED"] == "valor citado"


def test_mcp_main_parses_stdio_and_sse(monkeypatch) -> None:
    calls: list[dict[str, object]] = []

    def fake_create_server(config_path, *, host, port):
        calls.append({"config_path": config_path, "host": host, "port": port})
        return FakeMcpServer(calls)

    monkeypatch.setattr(mcp_server, "create_server", fake_create_server)

    mcp_server.main(["--config", "eval/fixtures/config.yaml"])
    mcp_server.main(
        [
            "--config",
            "eval/fixtures/config.yaml",
            "--transport",
            "sse",
            "--host",
            "127.0.0.1",
            "--port",
            "19090",
        ]
    )

    assert calls[0] == {
        "config_path": "eval/fixtures/config.yaml",
        "host": "127.0.0.1",
        "port": 8090,
        "transport": "stdio",
    }
    assert calls[1] == {
        "config_path": "eval/fixtures/config.yaml",
        "host": "127.0.0.1",
        "port": 19090,
        "transport": "sse",
    }


def test_install_service_generates_systemd_units(tmp_path) -> None:
    repo = Path(__file__).resolve().parents[1]
    venv = tmp_path / "venv"
    bin_dir = venv / "bin"
    unit_dir = tmp_path / "units"
    bin_dir.mkdir(parents=True)
    (bin_dir / "python").write_text("#!/usr/bin/env sh\nexit 0\n", encoding="utf-8")
    (bin_dir / "python").chmod(0o755)

    env = {
        **os.environ,
        "IANEST_SKIP_INSTALL": "1",
        "IANEST_SYSTEMD_DIR": str(unit_dir),
    }
    subprocess.run(
        [
            "bash",
            str(repo / "install.sh"),
            "--service",
            "--venv",
            str(venv),
            "--rest-port",
            "18000",
            "--mcp-port",
            "18090",
        ],
        cwd=repo,
        env=env,
        check=True,
        capture_output=True,
        text=True,
    )

    rest_unit = (unit_dir / "ianest-rest.service").read_text(encoding="utf-8")
    mcp_unit = (unit_dir / "ianest-mcp.service").read_text(encoding="utf-8")

    assert f"WorkingDirectory={repo}" in rest_unit
    assert f"EnvironmentFile={repo}/.env" in rest_unit
    assert f"ExecStart={venv}/bin/uvicorn --factory ianest_core.rest:create_app --host 127.0.0.1 --port 18000" in rest_unit
    assert f"WorkingDirectory={repo}" in mcp_unit
    assert f"EnvironmentFile={repo}/.env" in mcp_unit
    assert (
        f"ExecStart={venv}/bin/python -m ianest_core.mcp_server --transport sse "
        "--host 127.0.0.1 --port 18090"
    ) in mcp_unit


class FakeMcpServer:
    def __init__(self, calls: list[dict[str, object]]) -> None:
        self.calls = calls

    def run(self, *, transport: str) -> None:
        self.calls[-1]["transport"] = transport
