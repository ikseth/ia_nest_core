#!/usr/bin/env bash
#
# Proposito:
#   Crear o reutilizar un entorno virtual e instalar IA_NEST Core en modo editable.
#
# Entradas:
#   --interfaces, --service, --instance-name NAME, --config PATH, --env-file PATH.
#   --working-directory PATH, --rest-host HOST, --rest-port PORT, --mcp-host HOST,
#   --mcp-port PORT, --venv PATH, --help.
#
# Salidas:
#   Entorno virtual instalado y, con --service, units systemd por instancia.
#
# Efectos:
#   Crea el venv, instala con pip y puede escribir units systemd.
#
# Requisitos:
#   Bash, Python >= 3.13, modulo venv y pip.
#
# Seguridad:
#   No lee secretos: systemd recibe una ruta de EnvironmentFile ya creada.

set -euo pipefail

INSTALL_INTERFACES=false
INSTALL_SERVICE=false
INSTANCE_NAME=core
VENV_PATH=.venv
REST_HOST=127.0.0.1
REST_PORT=8000
MCP_HOST=127.0.0.1
MCP_PORT=8090
REPO_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
CONFIG_PATH="$REPO_DIR/config/core.yaml"
ENV_FILE="$REPO_DIR/.env"
WORKING_DIRECTORY="$REPO_DIR"

usage() { sed -n '2,20p' "$0" | sed 's/^# \{0,1\}//'; }
error() { echo "error: $1" >&2; exit 2; }

service_user() {
  if [[ "${EUID:-$(id -u)}" -eq 0 && -n "${SUDO_USER:-}" ]]; then printf '%s\n' "$SUDO_USER"; else id -un; fi
}

write_rest_unit() {
  local path="$1" user="$2"
  cat >"$path" <<EOF_UNIT
[Unit]
Description=IA_NEST Core ${INSTANCE_NAME} REST interface
After=network.target

[Service]
Type=simple
User=$user
WorkingDirectory=$WORKING_DIRECTORY
EnvironmentFile=$ENV_FILE
ExecStart=$VENV_ABS/bin/uvicorn --factory ianest_core.rest:create_app --host $REST_HOST --port $REST_PORT
Restart=on-failure

[Install]
WantedBy=multi-user.target
EOF_UNIT
}

write_mcp_unit() {
  local path="$1" user="$2"
  cat >"$path" <<EOF_UNIT
[Unit]
Description=IA_NEST Core ${INSTANCE_NAME} MCP SSE interface
After=network.target

[Service]
Type=simple
User=$user
WorkingDirectory=$WORKING_DIRECTORY
EnvironmentFile=$ENV_FILE
ExecStart=$VENV_ABS/bin/python -m ianest_core.mcp_server --config $CONFIG_PATH --transport sse --host $MCP_HOST --port $MCP_PORT
Restart=on-failure

[Install]
WantedBy=multi-user.target
EOF_UNIT
}

generate_systemd_units() {
  local unit_dir user
  user="$(service_user)"
  if [[ "${EUID:-$(id -u)}" -eq 0 && -z "${IANEST_SYSTEMD_DIR:-}" ]]; then unit_dir=/etc/systemd/system; else unit_dir="${IANEST_SYSTEMD_DIR:-$REPO_DIR/dist/systemd}"; fi
  mkdir -p "$unit_dir"
  write_rest_unit "$unit_dir/ianest-$INSTANCE_NAME-rest.service" "$user"
  write_mcp_unit "$unit_dir/ianest-$INSTANCE_NAME-mcp.service" "$user"
  echo "units generados en $unit_dir"
  if [[ "${EUID:-$(id -u)}" -eq 0 && "$unit_dir" == /etc/systemd/system ]]; then
    systemctl daemon-reload
  fi
}

while [[ $# -gt 0 ]]; do
  case "$1" in
    --interfaces) INSTALL_INTERFACES=true; shift ;;
    --service) INSTALL_SERVICE=true; INSTALL_INTERFACES=true; shift ;;
    --instance-name|--config|--env-file|--working-directory|--rest-host|--rest-port|--mcp-host|--mcp-port|--venv)
      [[ $# -ge 2 ]] || error "$1 requiere un valor"
      case "$1" in
        --instance-name) INSTANCE_NAME="$2" ;;
        --config) CONFIG_PATH="$2" ;;
        --env-file) ENV_FILE="$2" ;;
        --working-directory) WORKING_DIRECTORY="$2" ;;
        --rest-host) REST_HOST="$2" ;;
        --rest-port) REST_PORT="$2" ;;
        --mcp-host) MCP_HOST="$2" ;;
        --mcp-port) MCP_PORT="$2" ;;
        --venv) VENV_PATH="$2" ;;
      esac
      shift 2 ;;
    --help|-h) usage; exit 0 ;;
    *) error "argumento no reconocido: $1" ;;
  esac
done

cd "$REPO_DIR"
PYTHON_BIN=''
for candidate in python3 python3.14 python3.13; do
  if command -v "$candidate" >/dev/null 2>&1 && "$candidate" -c 'import sys; raise SystemExit(sys.version_info < (3, 13))'; then
    PYTHON_BIN="$candidate"
    break
  fi
done
[[ -n "$PYTHON_BIN" ]] || error "se requiere Python >= 3.13 (python3, python3.14 o python3.13)"
PYTHON_VERSION="$($PYTHON_BIN -c 'import sys; print(".".join(map(str, sys.version_info[:2])))')"

if [[ ! -d "$VENV_PATH" ]]; then echo "creando venv en $VENV_PATH"; "$PYTHON_BIN" -m venv "$VENV_PATH"; else echo "reutilizando venv en $VENV_PATH"; fi
case "$VENV_PATH" in /*) VENV_ABS="$VENV_PATH";; *) VENV_ABS="$REPO_DIR/$VENV_PATH";; esac
VENV_PYTHON="$VENV_ABS/bin/python"
[[ -x "$VENV_PYTHON" ]] || error "python del venv no existe o no es ejecutable: $VENV_PYTHON"

if [[ "${IANEST_SKIP_INSTALL:-}" != 1 ]]; then
  "$VENV_PYTHON" -m pip install --upgrade pip
  if [[ "$INSTALL_INTERFACES" == true ]]; then INSTALL_TARGET='.[test,interfaces]'; else INSTALL_TARGET='.[test]'; fi
  "$VENV_PYTHON" -m pip install -e "$INSTALL_TARGET"
fi
if [[ "$INSTALL_SERVICE" == true ]]; then generate_systemd_units; fi
echo "instalacion completada"
