# 0001: DERIVE de coverage tolerante a ids no-string y granularidad explicita

Estado: implementada
Tipo: robustecimiento surgido del smoke real (patron v0.2-3)
Impacto de version: ninguno adicional (dentro de la linea v0.3.0)
Version objetivo: v0.3.0

## Problema

Primer smoke real del modo coverage (laboratorio, 2026-07-23):

1. El planner real devolvio `"id": 1` (entero); `_plan_coverage` exige
   ids string y aborta con `PlanParseError` antes de generar nada.
2. El planner derivo UNA unidad para una tarea con ocho elementos
   enumerables: la instruccion generica de DERIVE no transmite la
   granularidad "una unidad por elemento verificable", lo que hace
   inalcanzable el umbral del smoke (`chunk_index >= 2`).

Ambos son defectos genericos del orquestador, no del dominio ni del caso
(mismo criterio que los robustecimientos de parseo de v0.2-3).

## Cambio

En `_plan_coverage` (solo modo coverage; el pipeline v0.2 no se toca):

- Tolerancia de ids: los ids enteros (en `id` y en `depends_on`) se
  coercen a string; un `id` ausente o vacio se sintetiza posicional
  (`u<n>`). La unicidad sigue siendo obligatoria.
- Instruccion DERIVE: se explicita, de forma generica, que debe crearse
  una unidad por cada elemento verificable de la tarea y que los ids
  deben ser strings cortos.

## Criterios de aceptacion

- Un plan con ids enteros o sin ids se acepta y ejecuta (tests nuevos).
- Conformance 34/34 con el digest declarado SIN cambio (los fakes
  scriptados no dependen de la instruccion).
- pytest completo en verde con y sin extras.
- El smoke real de laboratorio queda dentro de umbral
  (`coverage_complete=true`, `chunk_index >= 2`).

## Archivos previstos

- `src/ianest_core/runtime/task_runtime.py`
- `tests/test_task_coverage.py`

## Resultado

Implementada y verificada el 2026-07-23:

- `_coerce_unit_id` acepta ids enteros y sintetiza `u<n>` para ids
  ausentes; unicidad tras coercion sigue exigida (2 tests nuevos).
- Instruccion DERIVE generica con granularidad explicita ("one unit per
  verifiable item"). Con ella el planner real paso de derivar 1 unidad a
  derivar 8 para la tarea enumerable del smoke.
- pytest 107 en verde; conformance 34/34 con digest identico
  (5aa67516...); pipeline intacto.
- Smoke de laboratorio dentro de umbral: task_done,
  coverage_complete=true, chunk_index=6 (>=2), 8/8 unidades, 0 fallos,
  48.4s. Detalle en local/lab/2026-07-23_coverage_smoke.md (no
  versionado).
