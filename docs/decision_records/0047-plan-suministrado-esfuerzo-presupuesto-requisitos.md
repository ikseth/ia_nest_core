# Decision 0047: el plan suministrado frente a esfuerzo, presupuesto y requisitos (enmienda de ADR 0040)

Fecha: 2026-08-14
Estado: reconciliado por el usuario (2026-08-14). Punto abierto, no bloqueante:
si extended devolvera el plan integro o solo los prompts (preguntado por el canal
de CR); si solo devuelve prompts, cada tarea entra por la via degradada de D3.
Enmienda a: ADR 0040 (plan explicito en `task.run`, `extended CR-0001`)
Depende de: ADR 0041 (criterios de gestion de tareas), ADR 0044 (presupuesto de
tokens), ADR 0045 (niveles de esfuerzo)

## Contexto

ADR 0040 se decidio el 2026-07-27 y NO se ha implementado: `task.plan`, la
entrada `plan`, `plan_source` y `replan_unavailable` no aparecen en `src/`, ni
en `tests/`, ni en la bateria, ni en `CORE_CONTRACT.md`. La linea v0.4 sigue
rotulada como propuesta en `docs/PLAN.md`.

Entre aquella decision y hoy aterrizaron tres ADR que cambiaron la etapa PLAN
por debajo de ella, y los tres estan implementados y publicados en v0.3.0:

- **ADR 0041**: PLAN extrae requisitos, comprueba cobertura, dispone de una
  renegociacion y declara degradaciones; `plan_ready` emite `requirements`,
  `plan_attempts`, `requirements_covered` y `uncovered_requirements`.
- **ADR 0044**: el presupuesto de tokens lo dimensiona el plan; la concesion
  `base + per_subtask * n` se otorga EN CADA PLAN PRODUCIDO y se acumula.
- **ADR 0045**: `max_subtasks` y los demas ejes de intencion los gobierna el
  nivel de `effort` de la peticion, no la config a secas.

ADR 0040 no habla de ninguno de los tres, porque no existian. Implementarlo hoy
al pie de la letra obligaria al implementador a inventarse tres reglas de
contrato. Esta enmienda las escribe. No revisa la decision de ADR 0040 -el plan
como dato de entrada sigue siendo la forma correcta-: la completa.

## Decision

### D1: el esfuerzo viaja con el plan, y lo explicito manda

`task.plan` acepta `effort` con el mismo vocabulario y la misma precedencia que
`task.run` (ADR 0045), y devuelve en `params` el nivel resuelto y los limites
efectivos con los que derivo el plan.

Cuando `task.run` recibe un `plan`:

- si NO recibe `effort`, usa el declarado en el plan, no `default_effort`;
- si recibe `effort` explicito, ese manda, y el plan se valida contra SUS
  limites: si no cabe, corta con `max_subtasks`, como cualquier otro plan.

Motivo: sin esta regla, el camino sano falla. Una capa que planifica con
`effort=high` (por ejemplo 12 subtareas), enriquece y vuelve a llamar sin
declarar esfuerzo, se encontraria su plan valido cortado por el `max_subtasks`
del nivel `medium` de fabrica. El round-trip queda coherente por defecto y el
consumidor conserva el mando si quiere otra cosa.

### D2: un plan suministrado concede presupuesto como uno derivado

La concesion de ADR 0044 se calcula sobre el plan que va a ejecutarse, venga de
donde venga: `base + per_subtask * n` con `n` las subtareas del plan
suministrado, concedida UNA vez al entrar en FAN-OUT.

- Una iteracion nueva concede, igual que hoy.
- `replan_unavailable` no concede nada: corta.

Motivo: la concesion esta hoy atada a la derivacion del planificador
(`_pipeline_token_grant`, invocado tras resolver el plan). Sin regla explicita,
una tarea con plan suministrado entraria con presupuesto cero y moriria en la
primera comprobacion. La regla no anade campos: reusa la aritmetica que ya
existe.

### D3: los requisitos viajan con el plan; si no vienen, se declara

`task.plan` devuelve los `requirements` que extrajo (id y enunciado), junto al
plan. Cuando `task.run` recibe un plan:

- si trae `requirements`, se comprueba la cobertura contra el plan suministrado
  y `plan_ready` los emite con `requirements_covered` y
  `uncovered_requirements`, como en el camino normal. **No hay renegociacion**:
  renegociar es replanificar, y con plan suministrado esta prohibido (ADR 0040).
  Un plan que no cubre sus requisitos se ejecuta igualmente y lo declara.
- si NO los trae, el core no los reinventa -eso seria llamar al planificador que
  la entrada `plan` viene a evitar- y declara una degradacion:
  `{stage: plan, reason: requirements_unavailable, action: skip_coverage_check}`,
  con `requirements: []` y `requirements_covered: false`.

Motivo: emitir `requirements_covered: true` sobre una lista vacia seria afirmar
algo que nadie comprobo. La maquinaria de degradacion declarada de ADR 0041 (I4)
existe justo para esto: decir lo que no se pudo hacer sin mentir en el resultado
ni inventar un corte. No amplia el catalogo de cortes tipados.

### D4: los contadores cuentan lo que dicen contar

`plan_attempts` cuenta DERIVACIONES del planificador. Con `plan_source=supplied`
vale 0, y `plan_ready` se emite igual, una vez, con el plan recibido.
`evaluation_attempts` no cambia: EVALUATE conserva su renegociacion propia e
independiente (ADR 0041), que no depende de quien escribio el plan.

## Lo que esta enmienda NO toca

- La decision de ADR 0040 y su reparto: la descomposicion se queda en el core,
  el enriquecimiento en la capa. No hay costura hacia arriba.
- El alcance `mode=pipeline`. `mode=coverage` sigue fuera: extended no lo pidio.
- La validacion del plan suministrado (`PlanParseError`,
  `PlanDependencyError`, `max_subtasks`) y `replan_unavailable`, tal como
  ADR 0040 los fijo.
- ADR 0035: no hay puerto, ni proveedor registrado, ni llamada saliente.

## Alternativas descartadas

- **Que `task.run` con plan suministrado use siempre `default_effort`.** Es el
  comportamiento por omision si no se decide nada, y rompe el caso de uso que
  motivo el CR-0001: la capa planifica alto, enriquece y se le corta el plan.
- **Que el desajuste de esfuerzo sea error tipado nuevo.** Anade taxonomia para
  un caso que la regla de precedencia ya resuelve sin ambiguedad.
- **Que el core re-extraiga los requisitos del prompt original cuando el plan no
  los trae.** Gasta una llamada al planificador -lo que la entrada `plan` viene
  a evitar- y ademas produciria requisitos que nadie garantiza que correspondan
  al plan enriquecido.
- **Emitir `requirements_covered` como valor desconocido (nulo).** Cambia el
  tipo de un campo publicado y obliga a todos los consumidores a distinguir tres
  estados; la degradacion declarada da la misma informacion con el mecanismo que
  ya existe.
- **No conceder presupuesto a los planes suministrados y exigir que la capa
  declare el suyo.** Pondria el presupuesto del motor en manos de quien lo
  consume; ADR 0044 lo fija como medida del core.

## Consecuencia

- `CORE_CONTRACT.md`: `task.plan` y la entrada `plan` se escriben ya con estas
  tres reglas incorporadas (fase v0.4-B1).
- Bateria (fase v0.4-B2), casos adicionales sobre los de ADR 0040: plan
  suministrado sin `effort` hereda el del plan; plan suministrado con `effort`
  explicito menor corta `max_subtasks`; presupuesto concedido sobre plan
  suministrado; plan sin requisitos emite la degradacion
  `requirements_unavailable`; `plan_attempts=0` con `plan_source=supplied`.
- Impacto de version: adicion compatible (PATCH por `meta POLITICA_SEMVER.md`),
  publicada dentro de la linea v0.4.0 junto a ADR 0040 y ADR 0046.
- `extended CR-0001` sigue `reformulado` hasta la entrega. La pregunta abierta
  hacia extended -si devolvera el plan integro o solo los prompts- condiciona D1
  y D3: si solo devuelve prompts, cada tarea entra por la via degradada.
