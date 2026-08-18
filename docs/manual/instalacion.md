# Instalacion

Dos caminos, segun tengas ya un backend (Ollama) o no:

- **A) Desde cero** (maquina Linux nueva, sin Ollama) -> `deploy/setup.sh`.
- **B) Ya tengo Ollama** -> declara su endpoint y no lo provisiona.

## A) Desde cero (sin Ollama)

Prerequisitos de sistema (el instalador los COMPRUEBA y te guia si faltan; NO
los instala, por ser especificos de tu distro): driver NVIDIA (`nvidia-smi`),
Docker, y NVIDIA Container Toolkit (`nvidia-ctk`). Detalle en
[backend-gpu.md](backend-gpu.md).

Con eso, un solo comando levanta backend + modelos + core + config + verificacion:

    git clone https://github.com/ikseth/ia_nest_core.git
    cd ia_nest_core
    sudo bash deploy/setup.sh

`deploy/setup.sh` hace: Ollama+GPU (compose) -> `install.sh` -> configuracion
efectiva -> `ianest model pull` -> verificacion final. Los modelos salen solo de
`core.yaml`; no hay una segunda lista en el instalador. Ve
[DESPLIEGUE.md](../DESPLIEGUE.md) para el fichero plano de configuracion,
`--print-config`, servicios e instalacion con backend existente.

## B) Ya tengo Ollama

Requisitos minimos de tu Ollama: accesible por HTTP con endpoint
OpenAI-compatible (p.ej. `http://localhost:11434/v1`) y al menos un modelo
descargado. Recomendado que use GPU ([backend-gpu.md](backend-gpu.md)).

    git clone https://github.com/ikseth/ia_nest_core.git
    cd ia_nest_core
    cp deploy/ejemplo.setup.conf local/core.setup.conf
    # Ajustar ENDPOINT=http://TU-OLLAMA:11434/v1 y PROVISION_BACKEND=false.
    bash deploy/setup.sh --config local/core.setup.conf

## Comprobar

    python -m pytest -q       # los tests pasan (algunos de interfaz se saltan sin --interfaces)
    ianest --help

## Detalle

- `install.sh`: `--interfaces` (extras MCP/REST), `--service` (systemd),
  `--venv RUTA`, `--instance-name`, `--rest-host`, `--rest-port`, `--mcp-host`
  y `--mcp-port`.
- Configuracion declarativa: `deploy/ejemplo.setup.conf` y
  [DESPLIEGUE.md](../DESPLIEGUE.md). `ianest init` sigue disponible para una
  configuracion local dentro del clon.
- Backend con GPU y su despliegue: [backend-gpu.md](backend-gpu.md).
- Interfaces REST/MCP y servicios: [interfaces.md](interfaces.md).
