# Instalacion

## Requisitos

- Python 3.13 y git.
- Para inferencia real: un backend OpenAI-compatible (p.ej. Ollama) con un
  modelo descargado, accesible por HTTP.

## Instalar

    git clone https://github.com/ikseth/ia_nest_core.git
    cd ia_nest_core
    bash install.sh                 # core basico
    # o, con las interfaces REST y MCP:
    bash install.sh --interfaces
    source .venv/bin/activate

Opciones de `install.sh`:
- `--interfaces`  instala tambien los extras MCP/REST.
- `--venv RUTA`   ruta del entorno virtual (por defecto `.venv`).

## Comprobar

    python -m pytest -q             # los tests deben pasar
    ianest --help

(Sin `--interfaces`, un par de tests de interfaz se saltan; es normal.)

## Variable de entorno del backend

El endpoint del backend va por variable de entorno, NO en el YAML. Copia la
plantilla y rellenala:

    cp .env.example .env
    # en .env:  OPENAI_COMPAT_BASE_URL=http://localhost:11434/v1

La CLI carga `.env` del directorio actual automaticamente. Para las interfaces
REST/MCP, exporta la variable o haz `source .env` antes de arrancar el
servidor (ver interfaces.md).
