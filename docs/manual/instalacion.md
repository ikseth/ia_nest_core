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

## Configuracion inicial

La forma rapida: `ianest init` crea `config/core.yaml` y `.env` por ti, y
valida:

    ianest init --endpoint http://localhost:11434/v1 --template lab
    # --template minimal (un modelo) | lab (roster multi-modelo)
    # sin --endpoint lo pregunta (default http://localhost:11434/v1)
    # --force sobrescribe si ya existen

A mano (alternativa): copia una plantilla y crea el `.env`:

    cp config/core.example.yaml config/core.yaml     # o config/core.lab.example.yaml
    echo 'OPENAI_COMPAT_BASE_URL=http://localhost:11434/v1' > .env

El endpoint va por variable de entorno, NUNCA en el YAML. La CLI y las
interfaces cargan `.env` del directorio actual automaticamente; arranca
siempre desde la raiz del repo.

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
