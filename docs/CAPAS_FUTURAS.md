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

## Modelo de control / verificacion de respuesta (conciencia)

Traducir y verificar la respuesta con un modelo de control (idea del usuario;
ver ADR 0025, alternativa descartada para el core). Pertenece a
`ia_nest_core_conscience`.

## Memoria avanzada

Estrategia de memoria (niveles, consolidacion). El core solo define la costura
(`MemoryPort`, ADR 0011). La estrategia real -> `ia_nest_core_extended` o repo
dedicado.

## Otros (mapa de repos)

- RAG, busqueda web -> `ia_nest_core_extended`.
- Integraciones (Home Assistant, Nextcloud) -> `ia_nest_external_*`.
- Agentes -> `ia_nest_agents`.
