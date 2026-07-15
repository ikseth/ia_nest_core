#!/usr/bin/env bash
#
# Proposito:
#   Preparar IA_NEST Core y, salvo --skip-backend, desplegar Ollama en Docker.
#
# Entradas:
#   --endpoint URL          Endpoint OpenAI-compatible. Por defecto: http://localhost:11434/v1.
#   --template NOMBRE       Plantilla de config: minimal o lab. Por defecto: lab.
#   --models "M1 M2"        Modelos de Ollama a descargar.
#   --skip-backend          Omite Docker/Ollama y configura solo el core.
#   --rest-port N           Puerto REST que se pasa a install.sh.
#   --mcp-port N            Puerto MCP que se pasa a install.sh.
#   --help                  Muestra esta ayuda.
#
# Salidas:
#   Venv .venv, config/core.yaml y .env configurados. Con backend activo,
#   contenedor Ollama y los modelos indicados disponibles localmente.
#
# Efectos:
#   Ejecuta Docker Compose, descarga imagenes/modelos y ejecuta install.sh.
#   No instala drivers, Docker ni NVIDIA Container Toolkit.
#
# Requisitos:
#   Bash, curl y Python 3.13. Sin --skip-backend: Docker; GPU y toolkit son
#   opcionales, aunque necesarios para aceleracion NVIDIA.
#
# Seguridad:
#   No usa hosts de laboratorio ni escribe secretos fuera de .env. Docker y pip
#   pueden descargar imagenes y paquetes desde sus registros configurados.

set -euo pipefail

DEFAULT_ENDPOINT="http://localhost:11434/v1"
DEFAULT_TEMPLATE="lab"
DEFAULT_MODELS="qwen2.5:7b mistral-nemo"
BACKEND_URL="http://localhost:11434"
OLLAMA_CONTAINER="ia_nest_ollama"
REPO_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
COMPOSE_FILE="$REPO_DIR/deploy/ollama.compose.yaml"

ENDPOINT="$DEFAULT_ENDPOINT"
TEMPLATE="$DEFAULT_TEMPLATE"
MODELS_VALUE="$DEFAULT_MODELS"
SKIP_BACKEND=false
REST_PORT=""
MCP_PORT=""

usage() {
  sed -n '2,29p' "$0" | sed 's/^# \{0,1\}//'
}

error() {
  echo "error: $1" >&2
  exit 1
}

check_python() {
  command -v python3.13 >/dev/null 2>&1 || error "se requiere Python 3.13; instala Python 3.13 y vuelve a ejecutar"
  local version
  version="$(python3.13 -c 'import sys; print(".".join(map(str, sys.version_info[:2])))')"
  [[ "$version" == "3.13" ]] || error "se requiere Python 3.13, encontrado $version"
}

check_backend_dependencies() {
  if command -v nvidia-smi >/dev/null 2>&1; then
    echo "driver NVIDIA detectado"
  else
    echo "warning: nvidia-smi no encontrado; Ollama puede ejecutarse en CPU" >&2
  fi

  command -v docker >/dev/null 2>&1 || error "Docker no encontrado; instala Docker y vuelve a ejecutar"
  docker compose version >/dev/null 2>&1 || error "Docker Compose no disponible; instala el plugin Docker Compose"

  if command -v nvidia-ctk >/dev/null 2>&1; then
    echo "NVIDIA Container Toolkit detectado"
  else
    echo "warning: nvidia-ctk no encontrado; para GPU ejecuta 'sudo nvidia-ctk runtime configure --runtime=docker' y reinicia Docker" >&2
  fi
}

wait_for_backend() {
  local attempt
  for ((attempt = 1; attempt <= 60; attempt++)); do
    if curl -fsS "$BACKEND_URL/api/tags" >/dev/null; then
      echo "Ollama disponible"
      return
    fi
    sleep 1
  done
  error "Ollama no respondio en $BACKEND_URL tras 60 segundos"
}

start_backend() {
  docker compose -f "$COMPOSE_FILE" up -d
  wait_for_backend

  local model
  local -a models
  read -r -a models <<<"$MODELS_VALUE"
  for model in "${models[@]}"; do
    [[ -n "$model" ]] || continue
    echo "descargando modelo $model"
    docker exec "$OLLAMA_CONTAINER" ollama pull "$model"
  done
}

install_core() {
  local -a install_args=(--interfaces)
  if [[ -n "$REST_PORT" ]]; then
    install_args+=(--rest-port "$REST_PORT")
  fi
  if [[ -n "$MCP_PORT" ]]; then
    install_args+=(--mcp-port "$MCP_PORT")
  fi
  bash "$REPO_DIR/install.sh" "${install_args[@]}"
}

configure_core() {
  "$REPO_DIR/.venv/bin/ianest" init --force --endpoint "$ENDPOINT" --template "$TEMPLATE"
}

verify_core() {
  "$REPO_DIR/.venv/bin/ianest" --config config/core.yaml runtime detect
  if "$REPO_DIR/.venv/bin/ianest" --config config/core.yaml prompt run --prompt "hola" --domain general; then
    echo "smoke prompt.run ok"
  else
    echo "warning: smoke prompt.run no completado; revisa el endpoint y los modelos" >&2
  fi
}

warn_if_backend_uses_cpu() {
  if curl -fsS "$BACKEND_URL/api/ps" | python3.13 -c '
import json
import sys

models = json.load(sys.stdin).get("models", [])
raise SystemExit(0 if any(model.get("size_vram") == 0 for model in models) else 1)
'; then
    echo "warning: Ollama tiene un modelo cargado sin VRAM; si ocurrio tras 'systemctl daemon-reload', ejecuta 'docker restart ia_nest_ollama'" >&2
  fi
}

check_endpoint() {
  if curl -sS --connect-timeout 3 -o /dev/null "$ENDPOINT"; then
    echo "endpoint responde: $ENDPOINT"
  else
    echo "warning: endpoint no responde: $ENDPOINT" >&2
  fi
}

while [[ $# -gt 0 ]]; do
  case "$1" in
    --endpoint)
      [[ $# -ge 2 ]] || error "--endpoint requiere una URL"
      ENDPOINT="$2"
      shift 2
      ;;
    --template)
      [[ $# -ge 2 ]] || error "--template requiere minimal o lab"
      TEMPLATE="$2"
      shift 2
      ;;
    --models)
      [[ $# -ge 2 ]] || error "--models requiere una lista entre comillas"
      MODELS_VALUE="$2"
      shift 2
      ;;
    --skip-backend)
      SKIP_BACKEND=true
      shift
      ;;
    --rest-port)
      [[ $# -ge 2 ]] || error "--rest-port requiere un puerto"
      REST_PORT="$2"
      shift 2
      ;;
    --mcp-port)
      [[ $# -ge 2 ]] || error "--mcp-port requiere un puerto"
      MCP_PORT="$2"
      shift 2
      ;;
    --help|-h)
      usage
      exit 0
      ;;
    *)
      error "argumento no reconocido: $1"
      ;;
  esac
done

case "$TEMPLATE" in
  minimal|lab) ;;
  *) error "--template debe ser minimal o lab" ;;
esac

cd "$REPO_DIR"
check_python

if [[ "$SKIP_BACKEND" == true ]]; then
  echo "backend omitido por --skip-backend"
  check_endpoint
else
  check_backend_dependencies
  start_backend
fi

install_core
configure_core
verify_core

if [[ "$SKIP_BACKEND" == false ]]; then
  warn_if_backend_uses_cpu
fi

echo "setup completado"
