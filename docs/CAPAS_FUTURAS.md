# Capas futuras (concerns fuera del core)

Registro de necesidades que NO pertenecen a `ia_nest_core` (por alcance /
anti-entropia) y que se resolveran en capas o repos externos. Se documentan
aqui para no perderlas y para alimentar la fase 10 (fronteras hacia repos
externos). Ver el mapa de repos en `IA_NEST_CORE_CONTEXT.md`.

## Monitorizacion / watcher del backend

Un elemento que vigile de forma continua el estado del backend (Ollama) y su
uso de GPU (p.ej. detectar que un `systemctl daemon-reload` tiro la GPU del
contenedor y Ollama cayo a CPU; ver ADR 0028 y `docs/manual/backend-gpu.md`).

- Lo que SI hara el core: exponer el **dato** (readiness: GPU presente en el
  host vs backend usando la GPU) en `runtime health`/`detect`. Es observabilidad
  puntual, dentro del core.
- Lo que NO hara el core: un **watcher** que monitorice/alerte/actue de forma
  continua. Eso es ops/observabilidad, propio de una capa externa (p.ej.
  `ia_nest_core_ops` o un modulo de monitorizacion).

## Conscience: supervisor etico/de personalidad (dual live/sueno)

Definida en ADR 0034. Supervisor que puede bloquear/replantear en caliente
(modo live, sobre checkpoints del orquestador v0.2) y que en modo sueno hace
quiesce del core y revisa la telemetria del dia (JSONL/CSV) para aprender y
generar nuevas tramas de memoria. Sedimenta sus resoluciones (debates eticos y
de personalidad) como memoria de comportamiento en `extended`. Incluye el
modelo de control/verificacion de respuesta (ADR 0025, alternativa descartada
para el core). Pertenece a `ia_nest_core_conscience`.

Necesitara del core (linea v0.2, cada una con su ADR): checkpoints de
supervision en el orquestador y capacidad administrativa de quiesce.

## Memoria avanzada

Estrategia de memoria (niveles, consolidacion, memoria de comportamiento de
conscience). Via 2 (ADR 0031/0034): la estrategia Y la ejecucion viven en
`ia_nest_core_extended`; el core aporta la identidad de segmentacion como
clave. `MemoryPort` (ADR 0011) queda superado; retirada pendiente junto al
cambio de codigo.

## Comunicacion entidad-a-entidad

Varios entes IA_NEST comunicandose entre si (ADR 0033). Frontera futura del
ente; sin diseno asignado. Se registra para no perderla.

## Otros (mapa de repos)

- RAG, busqueda web -> `ia_nest_core_extended`.
- Integraciones (Home Assistant, Nextcloud) -> `ia_nest_external_*`.
- Agentes -> `ia_nest_agents`.
