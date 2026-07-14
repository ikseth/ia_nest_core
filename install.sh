#!/usr/bin/env bash
#
# Proposito:
#   Crear o reutilizar un entorno virtual local e instalar IA_NEST Core en modo editable.
#
# Entradas:
#   --interfaces  Instala tambien los extras de interfaz MCP/REST.
#   --service     Genera unidades systemd para REST y MCP SSE.
#   --rest-port N Puerto local del servicio REST. Por defecto: 8000.
#   --mcp-port N  Puerto local del servicio MCP SSE. Por defecto: 8090.
#   --venv PATH   Ruta del entorno virtual. Por defecto: .venv
#   --help        Muestra ayuda breve.
#
# Salidas:
#   Entorno virtual con el paquete instalado y mensajes de estado por stdout/stderr.
#
# Efectos:
#   Crea directorios del venv si no existen y ejecuta pip install dentro del venv.
#   Con --service, escribe units systemd; como root tambien ejecuta daemon-reload.
#   No modifica configuracion real ni archivos de secretos.
#
# Requisitos:
#   Bash, Python 3.13 disponible como python3.13 o python3, modulo venv y pip.
#
# Seguridad:
#   No conecta por red a hosts de laboratorio ni lee secretos. pip puede acceder a
#   indices configurados por el entorno local para descargar dependencias.

set -euo pipefail

INSTALL_INTERFACES=false
INSTALL_SERVICE=false
VENV_PATH=".venv"
REST_PORT="8000"
MCP_PORT="8090"
REPO_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

usage() {
  sed -n '2,25p' "$0" | sed 's/^# \{0,1\}//'
}

generate_systemd_units() {
  local unit_dir service_user env_file
  service_user="$(service_user)"
  env_file="$REPO_DIR/.env"
  if [[ "${EUID:-$(id -u)}" -eq 0 && -z "${IANEST_SYSTEMD_DIR:-}" ]]; then
    unit_dir="/etc/systemd/system"
  else
    unit_dir="${IANEST_SYSTEMD_DIR:-$REPO_DIR/dist/systemd}"
  fi
  mkdir -p "$unit_dir"

  write_rest_unit "$unit_dir/ianest-rest.service" "$service_user" "$env_file"
  write_mcp_unit "$unit_dir/ianest-mcp.service" "$service_user" "$env_file"

  echo "units generados en $unit_dir"
  if [[ "${EUID:-$(id -u)}" -eq 0 && "$unit_dir" == "/etc/systemd/system" ]]; then
    systemctl daemon-reload
    echo "para habilitar: systemctl enable ianest-rest.service ianest-mcp.service"
    echo "para arrancar: systemctl start ianest-rest.service ianest-mcp.service"
  else
    echo "para instalar como root:"
    echo "  sudo cp $unit_dir/ianest-*.service /etc/systemd/system/"
    echo "  sudo systemctl daemon-reload"
    echo "  sudo systemctl enable ianest-rest.service ianest-mcp.service"
    echo "  sudo systemctl start ianest-rest.service ianest-mcp.service"
  fi
}

service_user() {
  if [[ "${EUID:-$(id -u)}" -eq 0 && -n "${SUDO_USER:-}" ]]; then
    printf '%s\n' "$SUDO_USER"
  else
    id -un
  fi
}

write_rest_unit() {
  local path="$1"
  local user="$2"
  local env_file="$3"
  cat >"$path" <<EOF_UNIT
[Unit]
Description=IA_NEST Core REST interface
After=network.target

[Service]
Type=simple
User=$user
WorkingDirectory=$REPO_DIR
EnvironmentFile=$env_file
ExecStart=$VENV_ABS/bin/uvicorn --factory ianest_core.rest:create_app --host 127.0.0.1 --port $REST_PORT
Restart=on-failure

[Install]
WantedBy=multi-user.target
EOF_UNIT
}

write_mcp_unit() {
  local path="$1"
  local user="$2"
  local env_file="$3"
  cat >"$path" <<EOF_UNIT
[Unit]
Description=IA_NEST Core MCP SSE interface
After=network.target

[Service]
Type=simple
User=$user
WorkingDirectory=$REPO_DIR
EnvironmentFile=$env_file
ExecStart=$VENV_ABS/bin/python -m ianest_core.mcp_server --transport sse --host 127.0.0.1 --port $MCP_PORT
Restart=on-failure

[Install]
WantedBy=multi-user.target
EOF_UNIT
}

while [[ $# -gt 0 ]]; do
  case "$1" in
    --interfaces)
      INSTALL_INTERFACES=true
      shift
      ;;
    --service)
      INSTALL_SERVICE=true
      INSTALL_INTERFACES=true
      shift
      ;;
    --rest-port)
      if [[ $# -lt 2 ]]; then
        echo "error: --rest-port requiere un puerto" >&2
        exit 2
      fi
      REST_PORT="$2"
      shift 2
      ;;
    --mcp-port)
      if [[ $# -lt 2 ]]; then
        echo "error: --mcp-port requiere un puerto" >&2
        exit 2
      fi
      MCP_PORT="$2"
      shift 2
      ;;
    --venv)
      if [[ $# -lt 2 ]]; then
        echo "error: --venv requiere una ruta" >&2
        exit 2
      fi
      VENV_PATH="$2"
      shift 2
      ;;
    --help|-h)
      usage
      exit 0
      ;;
    *)
      echo "error: argumento no reconocido: $1" >&2
      usage >&2
      exit 2
      ;;
  esac
done

cd "$REPO_DIR"

if command -v python3.13 >/dev/null 2>&1; then
  PYTHON_BIN="python3.13"
elif command -v python3 >/dev/null 2>&1; then
  PYTHON_BIN="python3"
else
  echo "error: no se encontro python3.13 ni python3" >&2
  exit 1
fi

PYTHON_VERSION="$("$PYTHON_BIN" -c 'import sys; print(".".join(map(str, sys.version_info[:2])))')"
if [[ "$PYTHON_VERSION" != "3.13" ]]; then
  echo "error: se requiere Python 3.13, encontrado $PYTHON_VERSION en $PYTHON_BIN" >&2
  exit 1
fi

if [[ ! -d "$VENV_PATH" ]]; then
  echo "creando venv en $VENV_PATH"
  "$PYTHON_BIN" -m venv "$VENV_PATH"
else
  echo "reutilizando venv en $VENV_PATH"
fi

case "$VENV_PATH" in
  /*) VENV_ABS="$VENV_PATH" ;;
  *) VENV_ABS="$REPO_DIR/$VENV_PATH" ;;
esac

VENV_PYTHON="$VENV_ABS/bin/python"
if [[ ! -x "$VENV_PYTHON" ]]; then
  echo "error: python del venv no existe o no es ejecutable: $VENV_PYTHON" >&2
  exit 1
fi

if [[ "${IANEST_SKIP_INSTALL:-}" != "1" ]]; then
  echo "actualizando pip"
  "$VENV_PYTHON" -m pip install --upgrade pip

  if [[ "$INSTALL_INTERFACES" == true ]]; then
    INSTALL_TARGET=".[test,interfaces]"
  else
    INSTALL_TARGET=".[test]"
  fi

  echo "instalando $INSTALL_TARGET"
  "$VENV_PYTHON" -m pip install -e "$INSTALL_TARGET"
else
  echo "omitiendo instalacion por IANEST_SKIP_INSTALL=1"
fi

if [[ "$INSTALL_SERVICE" == true ]]; then
  generate_systemd_units
fi

echo "instalacion completada"
echo "activar: source $VENV_PATH/bin/activate"
