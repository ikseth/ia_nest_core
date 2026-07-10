# Plan

Estado: activo
Version: 1.1 - 2026-07-10 (auditado con Codex, reconciliado)

Fases segun `LINEA_DE_ACTUACION.md`. Regla: no se abre una fase sin validar
la anterior. Cada fase tiene criterio de salida falsable. Este documento no
acumula ideas sin decision.

## Fases 1-4: completadas

- Fase 1 Contexto IA: `IA_NEST_CORE_CONTEXT.md` (validado).
- Fase 2 Alcance: `ALCANCE_CORE.md` (validado).
- Fase 3 Arquitectura minima: `ARCHITECTURE.md` v0.8 (validado; ADRs 0003-0011).
- Fase 4 Contratos internos: `CORE_CONTRACT.md` + contexto de identidad
  (validado).

## Fase 5: Bateria de evaluacion (actual)

Objetivo: definir la bateria como CRITERIO DE ACEPTACION antes de
implementar, no como evaluacion de una implementacion ya hecha. Fija el
blanco para que la fase 6 no derive por inferencia.

Aclaracion: "bateria de evaluacion" aqui significa el conjunto de casos y el
veredicto esperado que la implementacion debera satisfacer. El motor que la
ejecuta (`eval.run`) se implementa en fase 6+ y consume esta bateria.

Dos pistas de evaluacion, separadas para no confundir determinismo con
calidad:

- Conformance determinista: casos ejecutados contra adaptadores FAKE. Salida
  reproducible bit a bit. Valida pipeline, ruteo, formato de traza y logica
  de veredicto. Es lo que da el veredicto "reproducible".
- Smoke de calidad: casos ejecutados contra un modelo local REAL. No dan
  veredicto reproducible (hay no-determinismo de muestreo); dan una senal de
  calidad y latencia dentro de umbrales.

Entregables:
- Conjunto declarativo de casos, etiquetados por pista (conformance | smoke),
  sin depender de servicios externos complejos.
- Formato de resultados de `eval.run` fijado (por caso: pista, veredicto,
  latencia, modelo usado, dominio usado).

Criterio de salida:
- Bateria escrita y revisada, con ambas pistas cubiertas.
- Cada caso de conformance tiene veredicto esperado reproducible.
- Cada caso de smoke tiene umbral de aceptacion (no veredicto exacto).
- Formato de resultados congelado.
- No requiere ejecucion (todavia no hay motor).

## Fase 6: Implementacion minima

Se parte en dos cortes para respetar "piezas pequenas". Cada corte tiene
criterio de salida propio.

### Fase 6a: vertical minimo de inferencia

Objetivo: el corte end-to-end mas fino posible (senal #1 de
`VISION_FUNCIONAL.md`: "responde por CLI con modelos locales").

Cadena: CLI -> prompt_runtime -> ModelAdapter (OpenAI-compatible, ADR 0003)
-> backend local, con modelo/dominio DECLARADO explicitamente (sin router
todavia; `prompt.run` admite dominio declarado por contrato). Incluye
identidad (default local configurado), traza minima (CSV+JSONL, ADR 0010) y
`NullMemoryAdapter` conectado (no-op, ADR 0011) para no crear deuda.

Criterio de salida:
- `prompt.run` responde por CLI con un modelo local real (smoke de calidad).
- Genera traza por request con identidad.
- La pista de conformance de la bateria pasa contra adaptador fake, con
  veredicto reproducible.

### Fase 6b: ruteo, resiliencia y runner de evaluacion

Objetivo: completar el core minimo operable (senal #2: "enruta dominios").

Anade: `domain_router` (reglas declarativas), politica de fallo de modelo
(ADR 0005), `config.validate` minimo, y el runner que ejecuta la bateria de
fase 5 (semilla de `eval.run`).

Criterio de salida:
- `domain.route` selecciona dominio/modelo por reglas y lo registra en traza.
- Politica de fallo (ADR 0005) verificada con al menos un caso: preferido no
  disponible -> alternativo -> error tipado.
- `config.validate` detecta una configuracion invalida.
- El runner ejecuta la bateria completa: conformance reproducible + smoke con
  umbrales.

## Fase 7: Interfaces MCP y REST minimas

Objetivo: exponer las capacidades del vertical por MCP y REST sin logica
distinta a la CLI (regla de paridad de `CORE_CONTRACT.md`). MCP usa el SDK
oficial (ADR 0009) con version declarada y verificable (ADR 0006); REST usa
un framework estandar (ADR 0009). La CLI de fase 6 es la referencia de
comportamiento.

Criterio de salida:
- Un cliente MCP externo ejecuta `prompt.run` con paridad a CLI.
- Un cliente REST ejecuta `prompt.run` con paridad a CLI.
- `runtime.health` declara la version MCP y es verificable.
- Ninguna de las dos capas contiene logica de negocio (misma capa de nucleo).

## Fase 8: Plan de repos/modulos externos

Objetivo: documentar las fronteras de handoff hacia los repos externos:
`MemoryPort` -> `ia_nest_core_extended`; conciencia ->
`ia_nest_core_conscience`; integraciones -> `ia_nest_external_*`; agentes ->
`ia_nest_agents`.

Criterio de salida:
- Contratos de frontera documentados y versionados.
- Checklist "Core cerrado significa" de `IA_NEST_CORE_CONTEXT.md` cumplido.

## Fuera de este plan

- Implementar memoria, RAG, web, conciencia o agentes (repos externos).
- La version MCP exacta (se fija en fase 7).
- Optimizacion de rendimiento antes de tener el vertical funcionando.
