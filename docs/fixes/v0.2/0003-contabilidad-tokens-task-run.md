# 0003: contabilidad real de tokens en los cortes de task.run

Estado: implementada
Tipo: correccion
Impacto de version: patch
Version objetivo: v0.2.x

## Problema

`TaskRuntime._limit_reason` evalua `max_context_tokens` solo contra
`simulated["context_tokens"]`. En ejecucion real ese valor es 0, por lo
que el corte `max_context_tokens` NUNCA dispara con backend real, pese a
que `ModelResponse` ya transporta `tokens_in`/`tokens_out` reales de cada
llamada (planner, subtareas, combiner, evaluator). El limite declarado en
la config es hoy inoperante fuera de conformance.

## Cambio

Acumular los tokens reales de todas las llamadas de la tarea en el estado
de la ejecucion y evaluar `max_context_tokens` contra ese acumulado.
`simulated` se conserva como override determinista para conformance, con
precedencia: `simulated` > acumulado real. La semantica del limite es la
ya implicita en el codigo: presupuesto acumulado de la tarea completa.

El acumulado real es ademas prerrequisito del corte `max_total_tokens`
del modo coverage (ADR 0038); esta ficha lo adelanta como correccion
independiente de la linea v0.2.

## Criterios de aceptacion

- Un `ScriptedFakeAdapter` con recuentos que exceden `max_context_tokens`
  provoca el corte `max_context_tokens` sin usar `simulated`.
- Con `simulated["context_tokens"]` presente, el comportamiento actual no
  cambia (precedencia del override).
- La bateria de conformance v0.2 no cambia de digest.
- El acumulado (tokens_in/tokens_out de la tarea) queda visible en la
  traza del resultado.
- pytest en verde con y sin extras; sin dependencias nuevas.

## Archivos previstos

- `src/ianest_core/runtime/task_runtime.py`
- `tests/test_task_runtime.py`
- `docs/fixes/v0.2/0003-contabilidad-tokens-task-run.md`

## Resultado

Se acumulan `tokens_in` y `tokens_out` de planner, subtareas, combiner y
evaluator en cada ejecucion de `task.run`, con sincronizacion para el fan-out.
`max_context_tokens` usa ese total salvo que exista
`simulated["context_tokens"]`, que mantiene su precedencia determinista.
La traza final expone ambos acumulados. Se anadieron 2 pruebas especificas;
la suite completa queda verificada sin dependencias nuevas.

Verificacion independiente (2026-07-23, revision Claude Code):

- pytest con extras: 83 passed; sin extras (venv limpio): 79 passed,
  4 skipped. Digest de conformance v0.2 sin cambio.
- Smoke en laboratorio con backend real (Ollama): con limite 4096 la
  tarea termina en task_done y la traza expone el acumulado real
  (592 in / 206 out); con limite 120 dispara el corte
  max_context_tokens con 690 tokens reales acumulados, corte imposible
  antes de esta ficha. Detalle en local/lab/2026-07-23_tokens_fix.md
  (no versionado).
