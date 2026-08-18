#!/usr/bin/env bash
#
# Proposito:
#   Instalar de forma declarativa IA_NEST Core y, por defecto, su backend Ollama.
#
# Entradas:
#   --config PATH          Fichero plano CLAVE=VALOR.
#   --print-config         Muestra la configuracion resuelta sin efectos.
#   --endpoint URL, --template NAME, --core-config PATH, --instance-name NAME.
#   --provision-backend BOOL, --skip-backend, --rest-host HOST, --rest-port PORT.
#   --mcp-host HOST, --mcp-port PORT, --service-install BOOL, --service-enable BOOL.
#   --verify strict|warn|skip, --help.
#
# Salidas:
#   Configuracion efectiva en /opt/ia_nest/config/<instancia>, estado separado y,
#   si se solicita, units systemd por instancia.
#
# Efectos:
#   Puede ejecutar Docker Compose, pip, systemctl y consultas al backend. --print-config
#   no ejecuta ninguna de esas acciones ni escribe ficheros.
#
# Requisitos:
#   Bash, curl, Python >= 3.13 y, con PROVISION_BACKEND=true, Docker.
#
# Seguridad:
#   El operador decide toda interfaz no local. Las interfaces no tienen autenticacion.

set -euo pipefail

readonly REPO_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
readonly COMPOSE_FILE="$REPO_DIR/deploy/ollama.compose.yaml"
readonly INSTALL_ROOT="/opt/ia_nest"
readonly -a CONFIG_KEYS=(
  INSTANCE_NAME ENDPOINT TEMPLATE CORE_CONFIG PROVISION_BACKEND REST_HOST REST_PORT
  MCP_HOST MCP_PORT SERVICE_INSTALL SERVICE_ENABLE VERIFY
)

declare -A VALUES=(
  [INSTANCE_NAME]=core
  [ENDPOINT]=http://localhost:11434/v1
  [TEMPLATE]=lab
  [CORE_CONFIG]=''
  [PROVISION_BACKEND]=true
  [REST_HOST]=127.0.0.1
  [REST_PORT]=8000
  [MCP_HOST]=127.0.0.1
  [MCP_PORT]=8090
  [SERVICE_INSTALL]=true
  [SERVICE_ENABLE]=false
  [VERIFY]=strict
)
declare -A SOURCES=()
declare -A ARGUMENTS=()
for key in "${CONFIG_KEYS[@]}"; do SOURCES["$key"]=default; done

CONFIG_FILE=''
PRINT_CONFIG=false

usage() {
  sed -n '2,25p' "$0" | sed 's/^# \{0,1\}//'
}

error() {
  echo "error: $1" >&2
  exit 1
}

set_argument() {
  ARGUMENTS["$1"]="$2"
}

load_config_file() {
  local path="$1" line key value line_number=0
  [[ -r "$path" ]] || error "no se puede leer --config: $path"
  while IFS= read -r line || [[ -n "$line" ]]; do
    line_number=$((line_number + 1))
    line="${line%$'\r'}"
    [[ -z "$line" || "$line" == \#* ]] && continue
    [[ "$line" == *=* ]] || error "$path:$line_number: se esperaba CLAVE=VALOR; este no es un core.yaml, usa deploy/ejemplo.setup.conf"
    key="${line%%=*}"
    value="${line#*=}"
    [[ -n "${VALUES[$key]+present}" ]] || error "$path:$line_number: clave desconocida '$key'; usa deploy/ejemplo.setup.conf como plantilla"
    VALUES["$key"]="$value"
    SOURCES["$key"]=file
  done < "$path"
}

apply_arguments() {
  local key
  for key in "${CONFIG_KEYS[@]}"; do
    if [[ -n "${ARGUMENTS[$key]+present}" ]]; then
      VALUES["$key"]="${ARGUMENTS[$key]}"
      SOURCES["$key"]=argument
    fi
  done
}

require_bool() {
  [[ "$2" == true || "$2" == false ]] || error "$1 debe ser true o false"
}

validate_config() {
  require_bool PROVISION_BACKEND "${VALUES[PROVISION_BACKEND]}"
  require_bool SERVICE_INSTALL "${VALUES[SERVICE_INSTALL]}"
  require_bool SERVICE_ENABLE "${VALUES[SERVICE_ENABLE]}"
  [[ "${VALUES[TEMPLATE]}" == minimal || "${VALUES[TEMPLATE]}" == lab ]] || error "TEMPLATE debe ser minimal o lab"
  [[ "${VALUES[VERIFY]}" == strict || "${VALUES[VERIFY]}" == warn || "${VALUES[VERIFY]}" == skip ]] || error "VERIFY debe ser strict, warn o skip"
  [[ "${VALUES[INSTANCE_NAME]}" =~ ^[A-Za-z0-9_-]+$ ]] || error "INSTANCE_NAME solo admite letras, numeros, guion y guion bajo"
  [[ "${VALUES[REST_PORT]}" =~ ^[0-9]+$ && "${VALUES[MCP_PORT]}" =~ ^[0-9]+$ ]] || error "REST_PORT y MCP_PORT deben ser numeros"
  [[ -n "${VALUES[REST_HOST]}" && -n "${VALUES[MCP_HOST]}" ]] || error "REST_HOST y MCP_HOST no pueden estar vacios"
  if [[ "${VALUES[SERVICE_INSTALL]}" == false && "${VALUES[SERVICE_ENABLE]}" == true ]]; then
    error "SERVICE_ENABLE=true requiere SERVICE_INSTALL=true"
  fi
  if [[ -n "${VALUES[CORE_CONFIG]}" && "${SOURCES[TEMPLATE]}" != default ]]; then
    error "CORE_CONFIG es excluyente con TEMPLATE; elimina TEMPLATE del fichero o argumento"
  fi
}

print_config() {
  local key
  for key in "${CONFIG_KEYS[@]}"; do
    printf '%s=%s (%s)\n' "$key" "${VALUES[$key]}" "${SOURCES[$key]}"
  done
}

check_python() {
  local candidate version
  for candidate in python3 python3.14 python3.13; do
    if command -v "$candidate" >/dev/null 2>&1; then
      version="$($candidate -c 'import sys; print(".".join(map(str, sys.version_info[:2])))')"
      if "$candidate" -c 'import sys; raise SystemExit(sys.version_info < (3, 13))'; then return; fi
    fi
  done
  error "se requiere Python >= 3.13; instala Python y vuelve a ejecutar"
}

check_backend_dependencies() {
  command -v docker >/dev/null 2>&1 || error "Docker no encontrado; instala Docker y vuelve a ejecutar"
  docker compose version >/dev/null 2>&1 || error "Docker Compose no disponible; instala el plugin Docker Compose"
}

backend_url() { printf '%s\n' "${VALUES[ENDPOINT]%/v1}"; }

wait_for_backend() {
  local attempt url
  url="$(backend_url)"
  for ((attempt = 1; attempt <= 60; attempt++)); do
    if curl -fsS "$url/api/tags" >/dev/null; then return; fi
    sleep 1
  done
  error "el backend no respondio en $url tras 60 segundos"
}

start_backend() {
  docker compose -f "$COMPOSE_FILE" up -d
  wait_for_backend
}

prepare_directories() {
  CONFIG_DIR="$INSTALL_ROOT/config/${VALUES[INSTANCE_NAME]}"
  STATE_DIR="$INSTALL_ROOT/state/${VALUES[INSTANCE_NAME]}"
  EFFECTIVE_CONFIG="$CONFIG_DIR/core.yaml"
  ENV_FILE="$CONFIG_DIR/.env"
  mkdir -p "$CONFIG_DIR" "$STATE_DIR" "$INSTALL_ROOT/repositories"
  if [[ "${EUID:-$(id -u)}" -eq 0 && -n "${SUDO_USER:-}" ]]; then
    chown "$SUDO_USER" "$CONFIG_DIR" "$STATE_DIR"
  fi
  chmod 700 "$CONFIG_DIR" "$STATE_DIR"
}

configure_core() {
  if [[ -n "${VALUES[CORE_CONFIG]}" ]]; then
    [[ -r "${VALUES[CORE_CONFIG]}" ]] || error "no se puede leer CORE_CONFIG: ${VALUES[CORE_CONFIG]}"
    cp "${VALUES[CORE_CONFIG]}" "$EFFECTIVE_CONFIG"
  else
    local template_file
    case "${VALUES[TEMPLATE]}" in
      minimal) template_file="$REPO_DIR/config/core.example.yaml" ;;
      lab) template_file="$REPO_DIR/config/core.lab.example.yaml" ;;
    esac
    cp "$template_file" "$EFFECTIVE_CONFIG"
  fi
  printf 'OPENAI_COMPAT_BASE_URL=%s\nIANEST_CONFIG=%s\n' "${VALUES[ENDPOINT]}" "$EFFECTIVE_CONFIG" > "$ENV_FILE"
  export OPENAI_COMPAT_BASE_URL="${VALUES[ENDPOINT]}"
  "$REPO_DIR/.venv/bin/ianest" --config "$EFFECTIVE_CONFIG" config validate
}

install_core() {
  local -a args=(--interfaces --venv "$REPO_DIR/.venv")
  if [[ "${VALUES[SERVICE_INSTALL]}" == true ]]; then
    args+=(--service --instance-name "${VALUES[INSTANCE_NAME]}" --config "$EFFECTIVE_CONFIG" --env-file "$ENV_FILE" --working-directory "$STATE_DIR" --rest-host "${VALUES[REST_HOST]}" --rest-port "${VALUES[REST_PORT]}" --mcp-host "${VALUES[MCP_HOST]}" --mcp-port "${VALUES[MCP_PORT]}")
  fi
  bash "$REPO_DIR/install.sh" "${args[@]}"
}

wait_for_port() {
  # systemd da por arrancado un servicio Type=simple en cuanto hace fork, no
  # cuando el proceso escucha. Comprobar en ese instante es una carrera que se
  # pierde siempre: hay que esperar al puerto, que es el hecho que importa.
  local host="$1" port="$2" nombre="$3" intento
  for ((intento = 1; intento <= 30; intento++)); do
    if timeout 2 bash -c "cat < /dev/null > /dev/tcp/$host/$port" 2>/dev/null; then
      return 0
    fi
    sleep 1
  done
  error "$nombre no escucha en $host:$port tras 30 segundos"
}

enable_services() {
  [[ "${VALUES[SERVICE_ENABLE]}" == true ]] || return
  local rest="ianest-${VALUES[INSTANCE_NAME]}-rest.service"
  local mcp="ianest-${VALUES[INSTANCE_NAME]}-mcp.service"
  systemctl enable --now "$rest" "$mcp"
  wait_for_port "${VALUES[REST_HOST]}" "${VALUES[REST_PORT]}" "REST"
  wait_for_port "${VALUES[MCP_HOST]}" "${VALUES[MCP_PORT]}" "MCP"
  # Despues del puerto, el estado: un servicio en bucle de reinicio pasa por
  # `active` a ratos, asi que preguntar solo por `is-active` no basta.
  systemctl is-active --quiet "$rest" || error "$rest no quedo activo"
  systemctl is-active --quiet "$mcp" || error "$mcp no quedo activo"
  curl -fsS "http://${VALUES[REST_HOST]}:${VALUES[REST_PORT]}/runtime/health" >/dev/null \
    || error "REST escucha pero no responde en /runtime/health"
}

report_backend_gpu() {
  local output
  output="$("$REPO_DIR/.venv/bin/ianest" --config "$EFFECTIVE_CONFIG" runtime health --json)" || return 0
  printf '%s' "$output" | "$REPO_DIR/.venv/bin/python" - <<'PY' >&2
import json
import sys

try:
    entries = json.load(sys.stdin)["backend"]["gpu"]
except Exception:
    sys.exit(0)
for entry in entries:
    if entry.get("status") == "in_use":
        continue
    motivo = entry.get("reason") or entry.get("status")
    modelos = ", ".join(entry.get("models") or [])
    print("warning: backend.gpu=%s (%s) para: %s" % (entry.get("status"), motivo, modelos))
PY
}

verify_core() {
  [[ "${VALUES[VERIFY]}" == skip ]] && return
  local status=0
  # La inferencia va PRIMERO, y la sonda de GPU despues. El backend solo declara
  # lo que tiene CARGADO: en una instalacion recien hecha no hay nada, asi que
  # consultar antes daria unknown/no_models_loaded SIEMPRE, y un aviso que salta
  # en cada instalacion es un aviso que nadie lee.
  "$REPO_DIR/.venv/bin/ianest" --config "$EFFECTIVE_CONFIG" prompt run --prompt hola --domain general || status=$?
  if [[ $status -eq 0 ]]; then
    report_backend_gpu
  fi
  if [[ $status -ne 0 ]]; then
    if [[ "${VALUES[VERIFY]}" == strict ]]; then error "verificacion fallida"; fi
    echo "warning: verificacion no completada" >&2
  fi
}

while [[ $# -gt 0 ]]; do
  case "$1" in
    --config) [[ $# -ge 2 ]] || error "--config requiere una ruta"; CONFIG_FILE="$2"; shift 2 ;;
    --print-config) PRINT_CONFIG=true; shift ;;
    --instance-name|--endpoint|--template|--core-config|--provision-backend|--rest-host|--rest-port|--mcp-host|--mcp-port|--service-install|--service-enable|--verify)
      [[ $# -ge 2 ]] || error "$1 requiere un valor"
      key="${1#--}"; key="${key//-/_}"; set_argument "${key^^}" "$2"; shift 2 ;;
    --skip-backend) set_argument PROVISION_BACKEND false; shift ;;
    --help|-h) usage; exit 0 ;;
    *) error "argumento no reconocido: $1" ;;
  esac
done

if [[ -n "$CONFIG_FILE" ]]; then load_config_file "$CONFIG_FILE"; fi
apply_arguments
validate_config
if [[ "$PRINT_CONFIG" == true ]]; then print_config; exit 0; fi

if [[ "${VALUES[REST_HOST]}" != 127.0.0.1 || "${VALUES[MCP_HOST]}" != 127.0.0.1 ]]; then
  echo "warning: una interfaz no local no tiene autenticacion; protege la red antes de exponerla" >&2
fi

cd "$REPO_DIR"
check_python
if [[ "${VALUES[PROVISION_BACKEND]}" == true ]]; then check_backend_dependencies; start_backend; fi
prepare_directories
install_core
configure_core
"$REPO_DIR/.venv/bin/ianest" --config "$EFFECTIVE_CONFIG" model pull
enable_services
verify_core
echo "setup completado: instancia ${VALUES[INSTANCE_NAME]}"
