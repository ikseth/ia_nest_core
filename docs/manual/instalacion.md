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

La CLI y las interfaces REST/MCP cargan `.env` del directorio actual
automaticamente. Arranca siempre desde la raiz del repo, donde estan `.env` y
`config/core.yaml`.

## Instalar como servicio (systemd, Linux)

Para arrancar REST y MCP de forma persistente, el instalador genera unidades
systemd:

    bash install.sh --service                              # puertos por defecto: REST 8000, MCP 8090
    bash install.sh --service --rest-port 8000 --mcp-port 8090

Genera `ianest-rest.service` e `ianest-mcp.service` (con `EnvironmentFile=.env`
y `Restart=on-failure`). Como root los escribe en `/etc/systemd/system` y hace
`daemon-reload`, pero **no los habilita ni arranca** (lo decides tu):

    sudo systemctl enable --now ianest-rest.service ianest-mcp.service

Sin root, los genera en `dist/systemd/` e indica como instalarlos. Las
interfaces que exponen se describen en [interfaces.md](interfaces.md).
