# 0008: rerun duplica los indices de subtarea en task.run pipeline

Estado: implementada
Tipo: correccion
Impacto de version: patch
Version objetivo: v0.3.0

## Problema

En `task.run` modo pipeline, cuando EVALUATE decide `rerun`, la segunda
iteracion re-ejecuta el plan y sus registros de subtarea se ANADEN a la lista
plana con `subtasks.extend(iteration_results)` (`task_runtime.py:217`). Cada
iteracion numera sus subtareas desde 0, asi que la lista final tiene indices
colisionantes.

Evidencia (reproducido con fakes): un plan de 3 subtareas con una decision
`rerun` produce en `task_done`:

    subtasks: index 0,1,2,0,1,2   (6 registros, 3 indices repetidos)

Cualquier consumidor -el parser del usuario, extended, conscience manana- lee
esto como subtareas repetidas. Es una de las causas del "se repite la
respuesta" que motivo esta revision. `CORE_CONTRACT.md` promete "arbol de
subtareas"; una lista plana con claves duplicadas no lo es.

## Cambio

Cada registro de subtarea gana un campo `iteration` (1-based), de modo que el
par `(iteration, index)` identifica univocamente cada subtarea a lo largo de la
tarea. `index` sigue siendo el indice dentro de su iteracion (no cambia su
semantica); `iteration` lo desambigua.

El campo se anade tambien a la telemetria por subtarea (JSONL), junto a
`subtask_index`, para que el arbol siga siendo reconstruible (ADR 0036).

## Consecuencia sobre la bateria

La bateria v0.2 (`orchestration.yaml`) asierta `subtasks` por
`_subtask_expectation`, que compara solo los campos declarados en `expect`
(dominio, modelo). El campo `iteration` es ADITIVO: los casos que no lo asertan
no cambian. Se anade al menos un caso (o se extiende el de `rerun`) que asierta
`iteration` para las dos iteraciones.

Verificar si el digest de conformance cambia: si algun caso existente asierta
la lista `subtasks` completa incluyendo un rerun, podria cambiar. Si cambia, es
por el campo aditivo y se DECLARA (patron v0.2-3/v0.3-2). Si no, se mantiene.

## Criterios de aceptacion

- Un plan con decision `rerun` produce registros de subtarea con `iteration`
  1 y 2; el par `(iteration, index)` es unico. Test lo cubre.
- `index` conserva su semantica (indice dentro de la iteracion).
- La telemetria por subtarea incluye `iteration`.
- pytest en verde con y sin extras.
- Digest: sin cambio, o declarado si el campo aditivo altera algun caso.
- Sin dependencias nuevas.

## Archivos previstos

- `src/ianest_core/runtime/task_runtime.py`
- `eval/battery/v0.2/orchestration.yaml` (si procede)
- `tests/test_task_runtime.py`

## No cubre

- Que `rerun` re-emita el checkpoint `plan_ready` con el MISMO plan (el `yield`
  esta dentro del bucle): es ruido de observabilidad, no un indice duplicado;
  se puede tratar aparte si molesta.
- Que `rerun` no realimente el juicio del evaluador a la re-ejecucion (repite
  los mismos prompts): es una decision de diseno mayor, no un bug; queda fuera.
- El modo coverage no tiene EVALUATE ni rerun (ADR 0038): no le aplica.

## Resultado

Cada registro de subtarea pipeline incorpora `iteration` 1-based, tanto en el
arbol devuelto como en la telemetria JSONL. `index` conserva el indice local de
la iteracion y el par `(iteration, index)` es unico en un rerun. La bateria
v0.2 aserta las dos iteraciones del caso de rerun; por ello el digest de
conformance cambia y queda declarado en `eval/README.md`.
