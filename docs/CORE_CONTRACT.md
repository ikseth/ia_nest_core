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
usuario (`prompt.run`, `prompt.stream`, `reasoning.run`, `reasoning.stream`,
`task.run`, `task.stream`, `domain.route`) transportan un contexto de identidad.
Las variantes de flujo lo transportan igual que sus hermanas bloqueantes: es la
misma capacidad con otro transporte. El core no implementa memoria (ADR 0035):
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

Dos campos de GPU, con dos significados que no se mezclan (ADR 0049):

- `gpu` describe el runtime LOCAL, la maquina donde corre el core. En un
  despliegue donde el backend vive en otro sitio, `available: false` es CIERTO y
  no es una regresion: esa maquina no tiene GPU.
- `backend.gpu` describe lo que el BACKEND declara sobre su propio uso de GPU:
  `status` con `in_use | cpu_only | unknown`, `models_loaded` y quien lo reporta.
  `cpu_only` es el valor que justifica el campo: un modelo que no cabe en memoria
  de video no falla, cae a CPU en silencio y responde un orden de magnitud mas
  lento.

La sonda del backend es especifica del proveedor y OPCIONAL, por la misma costura
y con el mismo patron de degradacion que el provisioning (ADR 0029): proveedor
que no se reconoce o backend que no contesta dan `unknown`. `runtime.health`
nunca falla por ella.

Declara ademas `core_version` (ADR 0046): la version del propio core, que es la
cifra con la que las capas de encima fijan su vinculo por SemVer (ADR 0032). Es
consulta de introspeccion: no requiere identidad.

### `capability.list`

Enumera las capacidades que el core expone y como se invocan (ADR 0046). Es
introspeccion: no requiere identidad.

El catalogo del que responde es la FUENTE UNICA de la que se derivan la CLI y
las rutas REST, y contra la que se asertan las herramientas MCP. No es una lista
mantenida aparte.

Debe devolver `core_version` y, por capacidad:

- nombre canonico y descripcion corta,
- si transporta identidad y si su respuesta es streaming,
- sus parametros (nombre, tipo, obligatoriedad, valores admitidos, defecto,
  metavar),
- su proyeccion en cada interfaz: ruta y metodo REST; grupo, accion, alias,
  textos de ayuda y banderas de render de la CLI; nombre de herramienta MCP.
  NULO en la interfaz donde no se expone.

Las capacidades que no se exponen en alguna interfaz se declaran igualmente, con
su hueco explicito. Los huecos vigentes y su motivo estan en ADR 0046:
`model.pull` e `init` son operacion de operador y viven solo en CLI;
`prompt.stream` y `reasoning.stream` no tienen forma en MCP.

Convencion de nombres, que es contrato porque las capas de encima derivan la
ruta del nombre (ADR 0046, enmienda D5-a): `X.run` es SIEMPRE bloqueante y
`X.stream` SIEMPRE flujo de eventos. En consecuencia `task.run` devuelve JSON
por `POST /task/run` y su flujo vive en `task.stream` -> `POST /task/stream`
(linea v0.4; hasta v0.3 `/task/run` era SSE).

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

Recibe un prompt y propone dominio, modelo y perfil. El enrutado es SEMANTICO
(ADR 0043): un modelo clasifica el prompt por su sentido contra el catalogo de
dominios (cada dominio con su `description`, que es la entrada normativa del
clasificador). No es un filtro de palabras clave.

Debe devolver:

- dominio seleccionado,
- confianza (la del clasificador, real),
- motivo breve,
- alternativas relevantes.

### `prompt.run`

Ejecuta un prompt contra el dominio declarado o el dominio por defecto. NO
orquesta ni enruta por sentido (ADR 0043): es el camino atomico y directo.

Resolucion de modelo por precedencia (ADR 0019, enmendado por ADR 0043): modelo
directo declarado > dominio declarado (usa su `preferred_model`) > dominio por
defecto (`general`). `prompt.run` NO invoca el router: quien quiera enrutado
semantico en una peticion atomica usa antes `domain.route`, o usa `task.run`.
El modelo resuelto debe existir en `models[]`.

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

### `task.plan` (linea v0.4: contrato fijado, implementacion pendiente)

Ejecuta SOLO la etapa PLAN de `task.run` y devuelve el plan sin ejecutarlo
(ADR 0040, enmendado por ADR 0047). Alcance `mode=pipeline`.

Acepta `effort` con el mismo vocabulario y la misma precedencia que `task.run`
(ADR 0045).

Debe devolver:

- por subtarea: `index`, `prompt`, `domain` ya resuelto con la precedencia del
  ADR 0019, `domain_hint_ignored` cuando proceda y `depends_on`,
- los `requirements` extraidos (id y enunciado),
- `params`, con el `effort` resuelto y los limites efectivos con los que se
  derivo el plan,
- trazabilidad.

No ejecuta subtareas, ni COMBINE, ni EVALUATE. La descomposicion se queda en el
core; quien quiera enriquecer cada subtarea lo hace entre esta capacidad y
`task.run` (ADR 0031, via 2).

### `task.run`

Ejecuta una tarea compleja orquestando los modelos del roster (ADR 0036):
descompone en subtareas (PLAN), enruta cada una (ROUTE, precedencia ADR 0019;
router semantico ADR 0043), ejecuta en fan-out (paralelo si independientes),
combina (COMBINE) y evalua e itera dentro de limites (EVALUATE, con
re-ejecucion o re-planificacion).

`task.run` NO recibe dominio de nivel superior, y no lo tendra (ADR 0043):
forzar un dominio unico a toda la tarea contradice la orquestacion. Cada
subtarea se enruta por su propio sentido. Quien quiera fijar un dominio, usa
`prompt.run`.

Debe tener:

- checkpoints observables del flujo D2: `task_received`, `plan_ready`,
  `subtask_done`, `combine_ready`, `iteration_end`, `task_done`,
- cortes tipados: `task_done | max_subtasks | max_iterations | max_replans |
  max_time | max_total_tokens | error`, mas `replan_unavailable` cuando el plan
  viene suministrado (linea v0.4),
- limites configurables (seccion `orchestration` de la config; incluye
  re-planificaciones y tope de paralelismo),
- identidad propagada a cada subtarea,
- telemetria por subtarea con `task_id` y vinculo al request padre.

Entrada de esfuerzo (ADR 0045): `task.run` acepta `effort` opcional con
vocabulario fijo `low | medium | high`. Si se omite, usa
`orchestration.default_effort`, cuyo valor de fabrica es `medium`. Un valor
fuera del vocabulario es `ConfigError` con `field=effort`.

`orchestration.effort` declara limites por nivel. La precedencia es una sola
regla, campo a campo: lo declarado por el nivel sustituye a la base y lo no
declarado cae a la base. El bloque base ES `medium`; un nivel no declarado es
un nivel vacio y resuelve por completo a esa base.

El nivel gobierna los ejes de intencion `max_subtasks`, `max_iterations`,
`max_replans`, `max_time_s`, `coverage.max_chunks` y
`coverage.max_retries_per_unit`. No gobierna los ejes de maquina
`max_parallel`, `coverage.units_per_chunk` y
`coverage.max_no_progress_iterations`, ni la medicion del coste
`token_budget`. Por el cable viaja solo el identificador del nivel, nunca
cifras.

Debe devolver:

- respuesta combinada final,
- motivo de corte,
- arbol de subtareas (modelo y dominio usados por cada una),
- parametros efectivos,
- trazabilidad,
- `requirements_covered` y `uncovered_requirements`, que declaran si el plan
  cubria los requisitos extraidos del prompt,
- `plan_attempts` y `evaluation_attempts` (1 o 2), contadores independientes
  de las etapas PLAN y EVALUATE,
- `degradations`, lista de degradaciones declaradas; vacia en el camino sano,
- `token_budget_total`, la suma de concesiones de presupuesto vigente.
- `params.effort`, el nivel resuelto, junto a todos los limites efectivos
  resueltos campo a campo.

Presupuesto de tokens (ADR 0044): `orchestration.token_budget` declara `base` y
`per_subtask`, y la concesion de una pasada es `base + per_subtask * n`; en
`coverage`, `base + per_subtask * n * (1 + max_retries_per_unit)`, porque los
reintentos por unidad son gasto autorizado por contrato. Se concede en cada plan
producido y se ACUMULA, y el gasto de la tarea se mide contra la suma.

**El presupuesto decide si empieza otra pasada; nunca mutila la que esta en
curso.** La pasada en marcha termina entera, asi que nunca se corta entre el
fan-out y el combinado, y si el evaluador dice `done` -o la cobertura queda
completa- el corte es `task_done` aunque el gasto haya superado el presupuesto:
agotar el presupuesto DESPUES de terminar bien no es un corte. Una re-derivacion
de PLAN gasta de la concesion en curso y no concede otra; una re-planificacion y
una iteracion nueva si conceden.

`orchestration.max_context_tokens` quedo RETIRADO por ADR 0044 y se ignora si
aparece. `reasoning.run` conserva el suyo, de perfil, con el sentido del
ADR 0008: son cosas distintas.

PLAN declara en cada `plan_ready` los campos aditivos `requirements` (id y
enunciado), `plan_attempts`, `requirements_covered` y
`uncovered_requirements`. La emision cuenta derivaciones: ocurre una vez por
plan producido, incluida cada re-planificacion, y no se repite por `rerun`.

Regla de renegociacion por etapa (ADR 0041): PLAN dispone de una sola
renegociacion por tarea, compartida por forma, requisitos huerfanos y
`max_subtasks`; EVALUATE dispone de otra propia e independiente cuando la
decision no es entendible. Cada contador esta fijado en 1 por contrato y no es
configurable. `evaluation_attempts` viaja tambien en `iteration_end`.

Regla de degradacion declarada (I4): si PLAN sigue siendo inservible tras
renegociar, usa una subtarea con el prompt integro y lo declara; si EVALUATE
sigue sin producir `done | rerun | replan`, asume `done` y declara
`{stage: evaluate, reason: undecipherable_decision, action: assume_done}`. Una
degradacion no es un corte, no amplia el catalogo de cortes tipados y conserva
el resultado ya producido.

Entrada `plan` opcional (ADR 0040, enmendado por ADR 0047; linea v0.4:
contrato fijado, implementacion pendiente). Alcance `mode=pipeline`. Sin `plan`,
`task.run` se comporta exactamente como sin esta entrada: opt-in, cero
regresion.

Con `plan` suministrado:

- el core no llama al planificador: valida el plan con las reglas ya vigentes y
  sus errores tipados -forma (`PlanParseError`), ciclos o indices invalidos
  (`PlanDependencyError`), tamano (corte `max_subtasks`)- y entra en FAN-OUT;
- NO se re-planifica: si EVALUATE decide `replan`, la tarea corta con
  `replan_unavailable`. `rerun` sigue disponible;
- `plan_ready` declara `plan_source`: `planner | supplied`;
- el esfuerzo lo hereda del plan si la peticion no declara `effort`; si lo
  declara, manda el explicito y el plan se valida contra sus limites;
- concede presupuesto como cualquier plan (`base + per_subtask * n`, ADR 0044),
  una vez, al entrar en FAN-OUT;
- si el plan trae `requirements`, se comprueba cobertura contra el y se declara,
  sin renegociar; si no los trae, el core no los reinventa y declara la
  degradacion `{stage: plan, reason: requirements_unavailable, action:
  skip_coverage_check}` con `requirements_covered=false`;
- `plan_attempts` vale 0, porque cuenta derivaciones del planificador.

Modos de ejecucion (ADR 0038, linea v0.3): el consumidor selecciona el
modo de forma explicita; no hay promocion automatica.

- `mode=pipeline` (default): el flujo de 5 etapas anterior, sin cambios.
- `mode=coverage`: completitud semantica guiada por cobertura para tareas
  con unidades enumerables y verificables.

**La longitud de la respuesta de `pipeline` esta acotada por el `max_tokens` del
COMBINADOR.** En `pipeline` todo pasa por una sola llamada final que reescribe
los resultados, asi que la respuesta no puede superar lo que esa llamada pueda
emitir, por muchas subtareas que haya: anadir subtareas no alarga la respuesta,
obliga al combinador a comprimir mas. En `coverage` no ocurre, porque su
respuesta es el ensamblado determinista de los fragmentos aceptados (ADR 0038):
su longitud esta acotada por el numero de unidades por el techo de cada llamada,
no por una sola.

Medido en laboratorio (2026-08-11 y 2026-08-12, detalle en `local/lab/`): con el
mismo prompt y `max_tokens: 512`, `pipeline` entrego 2015 caracteres -su
combinador emitio exactamente sus 512 tokens de techo, comprimiendo 1878 tokens
de subtareas- mientras `coverage` entrego 5337 sin ningun `finish_reason=length`.
`coverage` resulto ademas mas eficiente (del orden de 1 token gastado por
caracter entregado, frente a 3 de `pipeline` con ese perfil) y mas rapido, porque
no paga combinador ni evaluador.

Criterio de seleccion, por tanto: `pipeline` para tareas que se responden
combinando; `coverage` cuando lo que se pide es EXTENSO o enumerable. Quien
necesite salida larga en `pipeline` debe subir el `max_tokens` del perfil del
combinador, no anadir subtareas.

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
`units_per_chunk`, `max_chunks`, `max_retries_per_unit`,
`max_no_progress_iterations`. Los limites globales de `orchestration`
(`max_time_s`, `max_parallel`, `max_subtasks` como techo de unidades
derivables) aplican tambien, incluido el presupuesto de tokens.
`coverage.max_total_tokens` quedo RETIRADO por ADR 0044: el presupuesto de
coverage se calcula igual que el de pipeline, con el factor de reintentos.

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
- `task.plan`: obtener la descomposicion sin ejecutarla, para intervenir
  entre el plan y su ejecucion (linea v0.4).
- `capability.list`: descubrir que capacidades hay y como se invocan, sin
  ejecutar ninguna (linea v0.4).

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
