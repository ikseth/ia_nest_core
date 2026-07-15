# Fronteras del core hacia las capas externas

El core (`ia_nest_core`) es pequeno y cerrado. Las capacidades que no le
pertenecen viven en repos/capas externas y se conectan por contratos de
frontera (costuras). Este documento fija esas fronteras. Ver el mapa de repos
en `IA_NEST_CORE_CONTEXT.md` y los concerns identificados en `CAPAS_FUTURAS.md`.

Principio: el core expone una costura estable; la capa externa implementa la
capacidad. El core no absorbe la logica de la capa (`ALCANCE_CORE.md`).

## Capas y fronteras

### ia_nest_core_extended (RAG, web, memoria)
- Memoria: frontera `MemoryPort` (ADR 0011), con `NullMemoryAdapter` por
  defecto en el core. La estrategia real (niveles, consolidacion) vive aqui.
- RAG y busqueda web: el core no los conoce; se ofrecen como herramientas
  externas (`tool_contracts`) o como enriquecimiento previo al prompt, siempre
  desde esta capa.

### ia_nest_core_conscience (control / verificacion / conciencia)
- Frontera: consume el core por sus contratos publicos (CLI/REST/MCP,
  `CORE_CONTRACT.md`). El modelo de control/verificacion de respuesta (ADR 0025,
  alternativa descartada para el core) y la "doble conciencia" viven aqui.

### ia_nest_external_* (integraciones: Home Assistant, Nextcloud, ...)
- Frontera: `tool_contracts` (ADR 0007). El core invoca la herramienta por
  contrato (denegar por defecto, human-in-the-loop en operaciones destructivas)
  y no absorbe su logica. Cada integracion es un `ia_nest_external_<nombre>`.

### ia_nest_agents (agentes que usan el core)
- Frontera: los contratos publicos del core (CLI/REST/MCP). Un agente consume
  `prompt.run`/`reasoning.run`/... como cualquier cliente; no vive en el core.

### Monitorizacion / ops (p.ej. ia_nest_core_ops)
- Frontera: `runtime.health`/`runtime detect` y la telemetria (CSV/JSONL,
  ADR 0010/0015). El core expone el ESTADO; un watcher/monitor externo lo
  consume y actua/alerta de forma continua (ver `CAPAS_FUTURAS.md`).

## tool_contracts (frontera generica de herramientas)

`tool_contracts` (ADR 0007) es la frontera hacia herramientas externas
(integraciones, RAG, etc.): denegar por defecto, scopes explicitos,
confirmacion humana en lo destructivo. Se planificara cuando exista una
herramienta concreta que lo justifique (ADR 0022).

## Regla para nuevas capacidades

Anti-entropia (`IA_NEST_CORE_CONTEXT.md`): una capacidad nueva no entra al core
si no necesita el estado interno del registry/router. En ese caso es capa
externa y se conecta por una de estas fronteras.
