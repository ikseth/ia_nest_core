# Instalacion

Dos caminos, segun tengas ya un backend (Ollama) o no:

- **A) Desde cero** (maquina Linux nueva, sin Ollama) -> `deploy/setup.sh`.
- **B) Ya tengo Ollama** -> instala el core y conectalo con `ianest init`.

## A) Desde cero (sin Ollama)

Prerequisitos de sistema (el instalador los COMPRUEBA y te guia si faltan; NO
los instala, por ser especificos de tu distro): driver NVIDIA (`nvidia-smi`),
Docker, y NVIDIA Container Toolkit (`nvidia-ctk`). Detalle en
[backend-gpu.md](backend-gpu.md).

Con eso, un solo comando levanta backend + modelos + core + config + verificacion:

    git clone https://github.com/ikseth/ia_nest_core.git
    cd ia_nest_core
    bash deploy/setup.sh

`deploy/setup.sh` hace: Ollama+GPU (compose) -> pull de modelos -> `install.sh`
-> `ianest init` -> verificacion final. Opciones: `--endpoint`, `--models`,
`--template minimal|lab`, `--skip-backend`.

## B) Ya tengo Ollama

Requisitos minimos de tu Ollama: accesible por HTTP con endpoint
OpenAI-compatible (p.ej. `http://localhost:11434/v1`) y al menos un modelo
descargado. Recomendado que use GPU ([backend-gpu.md](backend-gpu.md)).

    git clone https://github.com/ikseth/ia_nest_core.git
    cd ia_nest_core
    bash install.sh --interfaces
    source .venv/bin/activate
    ianest init --endpoint http://TU-OLLAMA:11434/v1 --template lab
    ianest --config config/core.yaml runtime detect       # verifica backend + GPU

## Comprobar

    python -m pytest -q       # los tests pasan (algunos de interfaz se saltan sin --interfaces)
    ianest --help

## Detalle

- `install.sh`: `--interfaces` (extras MCP/REST), `--service` (systemd),
  `--venv RUTA`, `--rest-port`, `--mcp-port`.
- Configuracion: `ianest init` o a mano ([configuracion.md](configuracion.md)).
- Backend con GPU y su despliegue: [backend-gpu.md](backend-gpu.md).
- Interfaces REST/MCP y servicios: [interfaces.md](interfaces.md).
