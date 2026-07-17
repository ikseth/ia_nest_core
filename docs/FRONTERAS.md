# Fronteras del core hacia las capas externas

El core (`ia_nest_core`) es pequeno y cerrado. Las capacidades que no le
pertenecen viven en repos/capas externas y se conectan por contratos de
frontera (costuras). Este documento fija esas fronteras. Ver el mapa de repos
en `IA_NEST_CORE_CONTEXT.md` y los concerns identificados en `CAPAS_FUTURAS.md`.

Principio: el core expone una costura estable; la capa externa implementa la
capacidad. El core no absorbe la logica de la capa (`ALCANCE_CORE.md`).

## Registro de capas

Indice y grafo de dependencias (ADR 0032). El core hospeda este registro; el
contrato de cada capa vive en su repo. "Depende de" se fija por version SemVer.

| Zona | Capa (repo) | Responsabilidad | Costura con el core | Depende de | Estado |
|---|---|---|---|---|---|
| Ente | `ia_nest_core` | El motor: enruta, infiere, itera; orquestacion multi-modelo en linea v0.2 (ADR 0034) | - | - | v0.1.0 |
| Ente | `ia_nest_extended` | La memoria/conocimiento: enriquecimiento (RAG, memoria, datos web) | Enriquecimiento sobre contratos publicos (ADR 0031) | core | primera capa (en diseno) |
| Ente | `ia_nest_core_conscience` | Mente voluntaria: control etico/personalidad, dual live/sueno (ADR 0034) | Checkpoints de supervision (v0.2) + telemetria | core, extended (memoria de comportamiento) | prevista |
| Ente | `ia_nest_core_pulse` | Mente involuntaria (sistema nervioso autonomo): observa telemetria de todos y regula parametros dentro de techos del core (ADR 0037) | `runtime.health` + telemetria + perillas del core | core, extended, conscience | prevista |
| Ente | `ia_nest_web` | La cara: GUI de gestion y presentacion | Contratos publicos + estado de pulse | core, extended, conscience, pulse | prevista |
| Exterior | `ia_nest_agents` | Agentes que consumen el ente (no dirigen su pensar, ADR 0033) | Contratos publicos | core (+ capas que use) | prevista |
| Exterior | `ia_nest_external_*` | Integraciones que ACTUAN | `tool_contracts` (ADR 0007, diferido) | core | diferida |
| Exterior | Otras entidades IA_NEST | Comunicacion entidad-a-entidad | Por definir | - | futura (`CAPAS_FUTURAS.md`) |

## Capas y fronteras

### ia_nest_extended (la memoria/conocimiento del ente)
Enriquecimiento de contexto: solo lectura, NO `tool_contracts` (ADR 0031).
Decidido (via 2): el enriquecimiento ocurre EN LA CAPA, encima del core. La
capa recupera (memoria/RAG/web), arma el prompt, llama a `prompt.run` y hace el
write-back con la respuesta. El core aporta la identidad de segmentacion
(`user_id`/`session_id`/`namespace`/...) como clave de indexacion.
- Memoria: la estrategia completa (tiers, consolidacion, y la memoria de
  comportamiento que sedimenta conscience, ADR 0034) vive aqui. `MemoryPort`
  (ADR 0011) queda superado por la via 2; su retirada del core se registrara
  junto al cambio de codigo.
- RAG y datos web: enriquecen el prompt con conocimiento acotado (RAG) y datos
  actuales (web). El core no los conoce; no son herramientas (ADR 0031).

### ia_nest_web (GUI web)
- Frontera: los contratos publicos del core (CLI/REST/MCP) y, cuando existan,
  los contratos de las capas que exponga (enriquecimiento, conscience). Es la
  interfaz de gestion y de usuario; no vive en el core. Depende de esas capas
  por version (ADR 0032).

### ia_nest_core_conscience (la mente supervisora)
- Supervisor etico/de personalidad del ente (ADR 0034), dual: modo live
  (supervisa checkpoints del flujo, puede bloquear/replantear contrastando con
  memoria etica) y modo sueno (quiesce del core + revision batch de la
  telemetria del dia).
- Frontera: contratos publicos + checkpoints de supervision del orquestador
  (linea v0.2 del core, ADR 0034) + telemetria CSV/JSONL (ADR 0010/0015).
- Sedimenta sus resoluciones como memoria de comportamiento (tier de la memoria
  de `extended`), que vuelve al core via enriquecimiento (ADR 0025/0031).
- El modelo de control/verificacion de respuesta (ADR 0025, alternativa
  descartada para el core) y la "doble conciencia" viven aqui.

### ia_nest_external_* (integraciones: Home Assistant, Nextcloud, ...)
- Frontera: `tool_contracts` (ADR 0007). El core invoca la herramienta por
  contrato (denegar por defecto, human-in-the-loop en operaciones destructivas)
  y no absorbe su logica. Cada integracion es un `ia_nest_external_<nombre>`.

### ia_nest_agents (agentes que usan el ente)
- Frontera: los contratos publicos del core (CLI/REST/MCP). Un agente consume
  `prompt.run`/`reasoning.run`/... como cualquier cliente; no vive en el core.
- Zona exterior (ADR 0033): un agente usa al ente, pero NO dirige su pensar;
  la orquestacion del pensamiento es del core (ADR 0034).

### ia_nest_core_pulse (mente involuntaria / sistema nervioso autonomo)
- Motor de monitorizacion headless del ente (ADR 0037), CPU/RAM. Observa la
  telemetria de todos (core, extended, conscience) y REGULA parametros tecnicos
  dentro de los techos del core, a frecuencia fija; sub-modo futuro por
  disparadores.
- Frontera: `runtime.health`/`runtime detect` + telemetria (CSV/JSONL,
  ADR 0010/0015) como entrada; las perillas del core (p.ej. limites de perfil)
  como salida. Actua fuera de banda (evento aparte, no dentro de `task.run`;
  preserva el determinismo).
- Subordinado a conscience (veto voluntario sobre lo involuntario). La GUI
  (`ia_nest_web`) presenta su estado; pulse no dibuja.

## tool_contracts (frontera generica de herramientas)

`tool_contracts` (ADR 0007) es la frontera hacia herramientas que ACTUAN
(integraciones con efecto): denegar por defecto, scopes explicitos, confirmacion
humana en lo destructivo. RAG, memoria y datos web NO son herramientas: son
enriquecimiento (ADR 0031). Se planificara cuando exista una herramienta
concreta que lo justifique (ADR 0022).

## Regla para nuevas capacidades

Anti-entropia (`IA_NEST_CORE_CONTEXT.md`): una capacidad nueva no entra al core
si no necesita el estado interno del registry/router. En ese caso es capa
externa y se conecta por una de estas fronteras.
