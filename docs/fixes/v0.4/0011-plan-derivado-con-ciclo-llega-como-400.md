# 0011: un plan derivado con dependencias circulares llega al consumidor como 400

Estado: propuesta (2026-10-20); entra en la tanda v0.4.1 de `docs/PLAN.md`
Tipo: incumplimiento de contrato en el runtime
Impacto de version: patch
Version objetivo: v0.4.1

Origen: hallazgo 1 de los avisos de `ia_nest_extended` del 2026-10-20
(`ia_nest_meta/docs/handoff/avisos_al_core_desde_extended_2026-10-20.md`).

## Problema

Unas dos de cada 48 llamadas, el planificador emite un plan `pipeline` cuyas
dependencias forman un ciclo. El propio core lo rechaza al validarlo
(`PlanDependencyError: pipeline plan contains a cycle`) y `task.run` responde
HTTP 400. Es intermitente: la misma peticion en otra sesion sale 200.

En el codigo, `_resolve_plan` solo recupera `PlanParseError`; cualquier otro
error de validacion sale tal cual. Un plan con ciclo o con indices fuera de rango
DERIVADO por el propio core llega al consumidor como si el consumidor se hubiera
equivocado, que es lo que significa un 400.

## Por que es un defecto y no una decision

El contrato ya lo resuelve. La regla I4 de `task.run` dice: si PLAN sigue siendo
inservible tras renegociar, usa una subtarea con el prompt integro y lo declara.
Un plan con dependencias invalidas es inservible. El runtime no cumple esa regla
para esta clase de inservible.

## Cambio

Solo en la via del planificador:

- un `PlanDependencyError` al validar un plan derivado se trata como un plan
  inservible: renegocia una vez (si la renegociacion esta permitida) diciendo el
  defecto, y si el plan sigue invalido cae a una subtarea con el prompt integro y
  declara `{stage: plan, reason: invalid_dependencies, action: single_subtask}`. Como el repliegue no trae requisitos, declara ademas
  `requirements_unavailable`, igual que hace hoy `unparseable_shape`;
- vale igual para `task.plan`, que usa el mismo camino.

No cambia:

- un plan SUMINISTRADO con ciclo o indices invalidos sigue siendo
  `PlanDependencyError`: ahi el error si es del consumidor;
- la comprobacion de `_fan_out`, que queda como red de seguridad.

Nota para `ia_nest_extended`: su reintento ante este error deja de dispararse
con el core corregido. No rompe nada, y lo puede retirar cuando quiera.

## Criterios de aceptacion

- Caso de conformidad: planificador que devuelve un plan con ciclo y luego uno
  valido -> se usa el segundo, `plan_attempts: 2`, sin degradacion.
- Caso de conformidad: planificador que devuelve dos planes con ciclo -> una
  subtarea con el prompt integro, degradacion `invalid_dependencies` declarada,
  respuesta 200.
- Caso de conformidad: plan suministrado con ciclo -> `PlanDependencyError`,
  igual que hoy.
- Ningun caso existente cambia de salida.

## Archivos previstos

- `src/ianest_core/runtime/task_runtime.py`
- `docs/CORE_CONTRACT.md` (vocabulario de la regla I4), bateria y
  `eval/README.md`
