#!/usr/bin/env bash
#
# Proposito:
#   Crear o reutilizar un entorno virtual local e instalar IA_NEST Core en modo editable.
#
# Entradas:
#   --interfaces  Instala tambien los extras de interfaz MCP/REST.
#   --venv PATH   Ruta del entorno virtual. Por defecto: .venv
#   --help        Muestra ayuda breve.
#
# Salidas:
#   Entorno virtual con el paquete instalado y mensajes de estado por stdout/stderr.
#
# Efectos:
#   Crea directorios del venv si no existen y ejecuta pip install dentro del venv.
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
VENV_PATH=".venv"

usage() {
  sed -n '2,21p' "$0" | sed 's/^# \{0,1\}//'
}

while [[ $# -gt 0 ]]; do
  case "$1" in
    --interfaces)
      INSTALL_INTERFACES=true
      shift
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

VENV_PYTHON="$VENV_PATH/bin/python"
if [[ ! -x "$VENV_PYTHON" ]]; then
  echo "error: python del venv no existe o no es ejecutable: $VENV_PYTHON" >&2
  exit 1
fi

echo "actualizando pip"
"$VENV_PYTHON" -m pip install --upgrade pip

if [[ "$INSTALL_INTERFACES" == true ]]; then
  INSTALL_TARGET=".[test,interfaces]"
else
  INSTALL_TARGET=".[test]"
fi

echo "instalando $INSTALL_TARGET"
"$VENV_PYTHON" -m pip install -e "$INSTALL_TARGET"

echo "instalacion completada"
echo "activar: source $VENV_PATH/bin/activate"
