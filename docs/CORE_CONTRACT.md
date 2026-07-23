# Core contract

Estado: validado (2026-07-10)

## Proposito

Definir la frontera publica de IA_NEST Core.

El core debe enrutar, ejecutar y evaluar prompts usando modelos locales,
dominios y configuracion declarativa.

## Interfaces publicas

El core debe exponer las mismas capacidades por:

- CLI,
- API REST,
- MCP.

## Contexto de identidad del request

Las capacidades que participan en sesion, razonamiento o trazabilidad de
usuario (`prompt.run`, `reasoning.run`, `task.run`, `domain.route`)
transportan un contexto de identidad. El core no implementa memoria (ADR 0035):
la identidad es la clave que `ia_nest_extended` usa para indexar la suya
(ver "Frontera de memoria" en `ARCHITECTURE.md`). Las capacidades
administrativas o de introspeccion (`runtime.health`, `model.list`,
`domain.list`, `config.validate`) NO lo requieren.

Campos:

- `user_id`
- `service` (ejemplos genericos: `local_cli`, `external_agent`,
  `integration_x`; el core no conoce nombres de modulos concretos)
- `session_id` (continuidad de sesion; opcional segun capacidad)
- `domain_tag`
- `namespace` (ejemplos: `facts`, `tasks`, `preferences`, `persona`, `ops`,
  `safety`)

Estos campos deben reflejarse en la traza (telemetria, ADR 0010).

Identidad por defecto: en uso local (CLI) existe una identidad local
CONFIGURADA por defecto (operador local con nombre), no un modo anonimo, de
modo que no haya que pasar identidad a mano en cada invocacion sin fragmentar
la continuidad de la entidad.

Motivo: si la identidad no viaja en el camino de inferencia desde el inicio,
incorporar memoria despues obliga a re-hilar identidad por todo el core. Se
incluye ahora aunque el core minimo no la use, para no crear deuda. Acotarla
a las capacidades de usuario/sesion evita rigidez innecesaria en las
administrativas.

## Capacidades minimas

### `runtime.health`

Informa del estado del runtime local.

Debe comprobar:

- proceso core,
- backend de modelos,
- disponibilidad basica de modelos,
- deteccion de GPU cuando aplique.

### `model.list`

Lista modelos conocidos y su estado.

Debe devolver:

- identificador,
- proveedor,
- disponibilidad,
- capacidades declaradas,
- perfil recomendado.

### `domain.list`

Lista dominios disponibles.

Debe devolver:

- identificador,
- descripcion corta,
- modelo preferido,
- politica de inferencia,
- estado.

### `domain.route`

Recibe un prompt y propone dominio, modelo y perfil.

Debe devolver:

- dominio seleccionado,
- confianza,
- motivo breve,
- alternativas relevantes.

### `prompt.run`

Ejecuta un prompt contra el dominio seleccionado o declarado.

Resolucion de modelo por precedencia (ADR 0019): modelo directo declarado >
dominio declarado (usa su `preferred_model`) > orquestador/router (o dominio
por defecto). El modelo resuelto debe existir en `models[]`.

Debe devolver:

- respuesta,
- modelo usado,
- dominio usado,
- parametros efectivos,
- trazabilidad minima.

### `reasoning.run`

Ejecuta razonamiento iterativo controlado.

Debe tener:

- limite de iteraciones,
- limite de tiempo,
- salida observable,
- capacidad de desactivar pasos no necesarios.

### `task.run` (linea v0.2: contrato fijado, implementacion en curso)

Ejecuta una tarea compleja orquestando los modelos del roster (ADR 0036):
descompone en subtareas (PLAN), enruta cada una (ROUTE, precedencia ADR 0019),
ejecuta en fan-out (paralelo si independientes), combina (COMBINE) y evalua e
itera dentro de limites (EVALUATE, con re-ejecucion o re-planificacion).

Debe tener:

- checkpoints observables del flujo D2: `task_received`, `plan_ready`,
  `subtask_done`, `combine_ready`, `iteration_end`, `task_done`,
- cortes tipados: `task_done | max_subtasks | max_iterations | max_replans |
  max_time | max_context_tokens | error`,
- limites configurables (seccion `orchestration` de la config; incluye
  re-planificaciones y tope de paralelismo),
- identidad propagada a cada subtarea,
- telemetria por subtarea con `task_id` y vinculo al request padre.

Debe devolver:

- respuesta combinada final,
- motivo de corte,
- arbol de subtareas (modelo y dominio usados por cada una),
- parametros efectivos,
- trazabilidad.

Modos de ejecucion (ADR 0038, linea v0.3): el consumidor selecciona el
modo de forma explicita; no hay promocion automatica.

- `mode=pipeline` (default): el flujo de 5 etapas anterior, sin cambios.
- `mode=coverage`: completitud semantica guiada por cobertura para tareas
  con unidades enumerables y verificables.

En modo coverage:

- PLAN deriva unidades de cobertura (id, descripcion verificable,
  `domain_hint` opcional, `depends_on` opcional, orden requerido).
- Cada llamada de generacion usa ventana nueva, se enruta por la
  precedencia del ADR 0019 y cubre un subconjunto acotado de unidades
  pendientes; unidades independientes pueden ejecutarse en paralelo
  (`max_parallel`).
- Una etapa de validacion separada (rol `validator`, declarativo como
  planner/combiner) determina que unidades quedaron realmente cubiertas;
  solo lo validado se acepta y emite.
- `finish_reason` es senal tecnica, no prueba de completitud semantica:
  `stop` con cobertura pendiente continua; `length` continua desde lo
  pendiente sin duplicar contenido aceptado. La terminacion semantica la
  decide solo la cobertura (`coverage_complete`).
- La respuesta final es el ensamblado determinista de los fragmentos
  aceptados en el orden requerido (sin reescritura global).

Checkpoints adicionales (aditivos al flujo D2): `answer_chunk` (fragmento
aceptado: `chunk_index`, `unit_ids`, texto; emision en orden con
retencion de prefijo contiguo) y `coverage_updated` (snapshot compacto
del ledger).

Cortes tipados adicionales (aditivos): `max_chunks | max_total_tokens |
no_progress`. En modo coverage `task_done` implica
`coverage_complete=true`; cualquier otro corte devuelve
`coverage_complete=false` con el detalle en el estado final de cobertura.

Debe devolver ademas (aditivo, modo coverage):

- fragmentos aceptados,
- estado final de cobertura (unidades requeridas, completadas, fallidas,
  pendientes),
- contadores efectivos (chunks, tokens acumulados, reintentos).

Config declarativa aditiva (`orchestration.coverage`): `validator`,
`units_per_chunk`, `max_chunks`, `max_total_tokens`,
`max_retries_per_unit`, `max_no_progress_iterations`. Los limites
globales de `orchestration` (`max_time_s`, `max_parallel`,
`max_subtasks` como techo de unidades derivables) aplican tambien.

Regla de compatibilidad: los consumidores de streaming deben tolerar
tipos de evento y valores de `stop_reason` que no conozcan; las
adiciones a ambos catalogos son cambios compatibles.

### `config.validate`

Valida configuracion declarativa.

Debe comprobar:

- modelos,
- dominios,
- perfiles,
- rutas,
- incompatibilidades basicas.

### `eval.run`

Ejecuta una bateria de evaluacion.

Debe devolver:

- resultados por caso,
- latencia,
- modelo usado,
- dominio usado,
- veredicto reproducible.

## Seleccion de capacidad

El consumidor (o agente) elige la capacidad de forma explicita; el core no
promociona una capacidad a otra de forma silenciosa (ADR 0038). Esto
permite disponer de modos ligeros y modos potentes con coste y latencia
previsibles.

Criterios de uso:

- `prompt.run`: peticion atomica; una llamada, una respuesta.
- `reasoning.run`: una respuesta que mejora por borrador y refinamiento.
- `task.run` (mode=pipeline): tarea descomponible en subtareas
  heterogeneas que se combinan.
- `task.run` (mode=coverage): tarea con unidades enumerables y
  verificables que debe completarse con garantia de cobertura.

`finish_reason=stop` no acredita completitud semantica: si el consumidor
necesita esa garantia, la capacidad correcta es `task.run` en modo
coverage.

## No capacidades

El core no implementa:

- RAG,
- busqueda web,
- Home Assistant,
- consciencia,
- agentes autonomos,
- frontend completo.

Estas capacidades deben entrar por repos o modulos externos.

## Reglas de compatibilidad

- Toda capacidad publica debe tener contrato versionado.
- Toda capacidad publica debe poder probarse sin servicios externos complejos.
- La CLI debe ser la primera interfaz verificable.
- MCP y REST no deben tener logica distinta a la CLI.

