# 0010: el merito gana al techo, y presupuesto puente de task.run

Estado: propuesta
Tipo: correccion (dos defectos independientes del mismo sintoma)
Impacto de version: patch
Version objetivo: v0.3.x, ANTES de la linea MINOR de ADR 0044/0045

Origen: punto P2 de ADR 0044, reconciliado por el usuario el 2026-08-10. Esta
ficha NO sustituye a ADR 0044: no arregla el crecimiento del presupuesto con el
plan. Deja `task.run` usable en el laboratorio mientras esa linea se congela,
se calibra y se implementa.

## Problema

Dos defectos independientes que se presentan como el mismo sintoma: "task run
falla mucho mientras prompt run va bien".

### A. El techo gana al merito

En `TaskRuntime.stream` el limite se evalua ANTES de mirar la decision del
evaluador (`task_runtime.py`, el bloque que va de `_limit_reason` a
`decision == "done"`). Una tarea que el evaluador dio por `done` sale con
`stop_reason = max_context_tokens`; la CLI imprime "Tarea cortada" y termina con
codigo 1 (regla I3, ADR 0041).

El test `test_task_runtime_limits_real_accumulated_tokens_and_traces_them`
guioniza el evaluador con `"done"` y AFIRMA como correcto ese resultado: la
expectativa equivocada esta congelada en la suite.

Afecta igual a `max_time`, que sale del mismo `_limit_reason`: una tarea que
termino bien pasado el tiempo declarado tambien se presenta como cortada.

El modo `coverage` NO tiene este defecto: alli el limite se comprueba al inicio
del ciclo y `task_done` se fija al final del anterior, con lo que una cobertura
completa sale del bucle antes de que el limite vuelva a mirarse. La asimetria es
del modo `pipeline`.

### B. El presupuesto por defecto no da para una pasada sana

Con los valores que publican el esquema y las DOS plantillas -`max_tokens: 512`
de perfil, `max_subtasks: 4`, `max_context_tokens: 4096`-, una pasada consume
`3 + n` llamadas (planificador, n subtareas, combinador, evaluador). Solo las
salidas son 7 x 512 = 3584, y la ENTRADA del combinador anade del orden de
4 x 512 = 2048 mas, porque recibe el JSON integro de cada registro de subtarea.

Una pasada correcta de cuatro subtareas no cabe en 4096, y `max_iterations: 2`
es inalcanzable: la segunda pasada nunca es pagable. Los limites que enviamos
por defecto son mutuamente incoherentes.

## Cambio

### A. El merito se comprueba antes que el limite

En el bucle de `pipeline`, la decision `done` del evaluador se comprueba ANTES
de `_limit_reason`. Orden nuevo: `done` -> limite -> `replan` -> `max_iterations`.

Es el mismo principio que fija ADR 0044 en su D1 -el presupuesto decide si
empieza otra pasada, no si la que acaba de terminar valio-, adelantado aqui
porque corrige un fallo observable por si solo. Aplica a los dos cortes que
produce `_limit_reason` (`max_context_tokens` y `max_time`): si la tarea termino
por merito propio, no hay proxima pasada que vetar.

`task_done` sigue reservado a la terminacion por merito propio (I3, ADR 0041);
lo que cambia es que agotar el presupuesto DESPUES de terminar bien deja de
contar como corte.

### B. Presupuesto por defecto a 16384

`max_context_tokens` de `orchestration` pasa de 4096 a 16384 en el esquema
(`OrchestrationConfig`) y en las dos plantillas.

Por que 16384 y no otro numero:

- cubre dos pasadas de cuatro subtareas al tope del perfil (unos 6600 por
  pasada), con lo que `max_iterations: 2` deja de ser inalcanzable;
- es el valor que YA lleva `coverage.max_total_tokens`, de modo que los dos
  modos dejan de discrepar en un factor de cuatro mientras dura el puente;
- es provisional por contrato: ADR 0044 lo sustituye por
  `base + per_subtask * n` y retira el campo.

No se toca `max_context_tokens` de `profiles` (ADR 0008, bucle de
`reasoning.run`), ni `max_subtasks`, ni ningun otro limite: su recalibracion
pertenece a la linea de ADR 0044/0045.

## Criterios de aceptacion

- Un evaluador que devuelve `done` con el presupuesto ya excedido produce
  `stop_reason = task_done` y codigo de salida 0 (test nuevo).
- Lo mismo con el tiempo excedido (`simulated: {elapsed_s: ...}`) y evaluador
  `done`: `task_done`, no `max_time` (test nuevo).
- Un evaluador que devuelve `rerun` con el presupuesto excedido sigue cortando
  con `max_context_tokens`, con respuesta no vacia y codigo distinto de cero
  (no regresion de I3). El test vigente
  `test_task_runtime_limits_real_accumulated_tokens_and_traces_them` se reescribe
  para guionizar `rerun`: conserva lo que de verdad probaba -la contabilidad real
  de tokens y su traza- y deja de congelar la expectativa equivocada.
- `mode=coverage` sin cambios de comportamiento (el defecto A no le afecta).
- Las dos plantillas y el esquema declaran 16384 y siguen validando
  (`config validate`); el test que comprueba que plantillas y esquema no divergen
  (`tests/test_init.py`) sigue en verde.
- **Digest de conformance SIN cambio.** Verificado sobre la bateria: los casos
  `task_stop_max_context` y `task_stop_max_time` guionizan
  `evaluate_decisions: [rerun]`, no `done`, de modo que la inversion de
  precedencia no los toca; y el nuevo default tampoco los alcanza, por dos vias
  independientes: la fixture `eval/fixtures/orchestration.yaml` declara su
  `max_context_tokens` de forma explicita, y ademas los casos usan `simulated`,
  que tiene precedencia sobre el acumulado real. Los casos de `coverage` con
  `simulated` miden `max_total_tokens`, que esta ficha no toca. Si el digest
  cambiase, es senal de que el cambio se fue de alcance.
- pytest en verde con y sin extras; sin dependencias nuevas.

## Archivos previstos

- `src/ianest_core/runtime/task_runtime.py` (orden del bucle de pipeline)
- `src/ianest_core/config/schema.py` (default de `OrchestrationConfig`)
- `config/core.example.yaml`, `config/core.lab.example.yaml`
- `tests/test_task_runtime.py` (test reescrito y dos tests nuevos)
- `docs/manual/configuracion.md` (el valor documentado)
- `CHANGELOG.md`

## No cubre

- El crecimiento del presupuesto con el plan: es ADR 0044 (D2), linea MINOR.
- El renombrado del corte a `max_total_tokens` y la unificacion con `coverage`:
  ADR 0044 (D3, punto P1 reconciliado). Este puente conserva el nombre viejo a
  proposito, para no tocar contrato ni digest.
- Los niveles de esfuerzo: ADR 0045.
- La recalibracion de `max_subtasks`, `max_iterations`, `max_replans` y
  `max_time_s`: ADR 0045 (D7), y depende de la puerta de laboratorio.

## Resultado

(pendiente de implementacion)
