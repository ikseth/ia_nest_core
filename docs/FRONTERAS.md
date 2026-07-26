# Fronteras del core hacia las capas externas

El core (`ia_nest_core`) es pequeno y cerrado. Las capacidades que no le
pertenecen viven en repos/capas externas y se conectan por contratos de
frontera (costuras). Este documento fija esas fronteras. Ver el mapa de repos
en `IA_NEST_CORE_CONTEXT.md` y los concerns identificados en `CAPAS_FUTURAS.md`.

Principio: el core expone una costura estable; la capa externa implementa la
capacidad. El core no absorbe la logica de la capa (`ALCANCE_CORE.md`).

## Registro de capas

Re-hogado. El indice de capas del ente y su grafo de dependencias viven en el
repo de gobernanza `ia_nest_meta`: `docs/REGISTRO_CAPAS.md`, junto con la regla
de vinculo entre capas (meta ADR 0003). Alli consta tambien la version publicada
y el estado de trabajo de cada repo.

Origen historico: este documento y ADR 0032. El motivo del movimiento: el
registro tiene zonas "Ente" y "Exterior", y el propio repo de gobernanza no cabe
en ninguna de las dos.

Lo que este documento sigue fijando es la COSTURA: que expone el core a cada
capa.

## Capas y fronteras

Este documento fija la costura del core. Donde el texto describe ademas la
doctrina INTERNA de una capa aun no sembrada (conscience, pulse, web), va
marcado `[doctrina de capa]`: es diseno reconciliado que se conserva aqui como
deuda declarada y que mudara al repo de esa capa cuando se siembre. No se
re-hoga a `ia_nest_meta`: meta gobierna COMO se construye el ente, no que hace
cada pieza por dentro (meta ADR 0003).

### ia_nest_extended (la memoria/conocimiento del ente)
Enriquecimiento de contexto: solo lectura, NO `tool_contracts` (ADR 0031).
Decidido (via 2): el enriquecimiento ocurre EN LA CAPA, encima del core. La
capa recupera (memoria/RAG/web), arma el prompt, llama a `prompt.run` y hace el
write-back con la respuesta. El core aporta la identidad de segmentacion
(`user_id`/`session_id`/`namespace`/...) como clave de indexacion.
- Memoria: la estrategia completa (tiers, consolidacion, y la memoria de
  comportamiento que sedimenta conscience, ADR 0034) vive en esa capa y se
  documenta en su repo (`docs/VISION_MEMORIA.md`, `docs/ROSTER_MEMORIA.md`,
  `docs/POLITICA_WRITEBACK.md` y sus ADR). `MemoryPort`
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
- `[doctrina de capa]` Supervisor etico/de personalidad del ente (ADR 0034), dual: modo live
  (supervisa checkpoints del flujo, puede bloquear/replantear contrastando con
  memoria etica) y modo sueno (quiesce del core + revision batch de la
  telemetria del dia).
- Frontera: contratos publicos + checkpoints de supervision del orquestador
  (linea v0.2 del core, ADR 0034) + telemetria CSV/JSONL (ADR 0010/0015).
- `[doctrina de capa]` Sedimenta sus resoluciones como memoria de comportamiento
  (tier de la memoria de `extended`), que vuelve al core via enriquecimiento
  (ADR 0025/0031).
- `[doctrina de capa]` El modelo de control/verificacion de respuesta (ADR 0025,
  alternativa descartada para el core) y la "doble conciencia" viven aqui.

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
- `[doctrina de capa]` Motor de monitorizacion headless del ente (ADR 0037), CPU/RAM. Observa la
  telemetria de todos (core, extended, conscience) y REGULA parametros tecnicos
  dentro de los techos del core, a frecuencia fija; sub-modo futuro por
  disparadores.
- Frontera: `runtime.health`/`runtime detect` + telemetria (CSV/JSONL,
  ADR 0010/0015) como entrada; las perillas del core (p.ej. limites de perfil)
  como salida. Actua fuera de banda (evento aparte, no dentro de `task.run`;
  preserva el determinismo).
- `[doctrina de capa]` Subordinado a conscience (veto voluntario sobre lo
  involuntario). La GUI (`ia_nest_web`) presenta su estado; pulse no dibuja.

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
