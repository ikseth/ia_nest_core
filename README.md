# IA_NEST Core

Nucleo IA local basado en dominios, orquestacion de modelos, configuracion
declarativa e interfaz MCP.

Este repositorio nace como extraccion conceptual de IA_NEST, no como migracion
directa del codigo existente.

## Orden de lectura

1. `IA_NEST_CORE_CONTEXT.md`
2. `docs/VISION_FUNCIONAL.md`
3. `docs/LINEA_DE_ACTUACION.md`
4. `docs/ALCANCE_CORE.md`
5. `docs/CORE_CONTRACT.md`
6. `docs/CONVENCIONES.md`
7. `docs/ARCHITECTURE.md`
8. `docs/PLAN.md`

## Alcance de este repo

Este repo contiene solo el core basico:

- modelos,
- dominios,
- orquestacion,
- runtime local,
- interfaz MCP del core,
- configuracion,
- instalacion y deteccion de runtime/GPU.

RAG, web, consciencia, GUI e integraciones viven en repos separados.

## Instalacion local

Requisitos:

- Python 3.13
- bash
- pip/venv

Instalacion basica:

```bash
./install.sh
source .venv/bin/activate
pytest
```

Instalacion con interfaces MCP/REST:

```bash
./install.sh --interfaces
source .venv/bin/activate
pytest
```

El script es idempotente: reutiliza `.venv` si ya existe. Para otra ruta:

```bash
./install.sh --venv /tmp/ianest_core_venv
```

## Configuracion local

La configuracion real y secretos no se versionan. Para preparar variables de
entorno:

```bash
cp .env.example .env
```

Rellena `.env` con valores locales. El endpoint OpenAI-compatible debe venir
por variable de entorno o configuracion local no versionada.

## Deteccion de runtime/GPU

La deteccion es local y no consulta hosts remotos:

```bash
ianest --config eval/fixtures/config.yaml runtime detect --json
```

Si `nvidia-smi` existe, reporta nombre y memoria de GPU. Si no existe o falla,
devuelve `available: false` sin romper la ejecucion.
