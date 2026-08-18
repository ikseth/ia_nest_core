# Bateria de evaluacion (fase 5)

La bateria es el CRITERIO DE ACEPTACION que la implementacion (fase 6) debera
satisfacer. Se define antes de implementar, para que el codigo no derive por
inferencia. El motor que la ejecuta (`eval.run`) llega en fase 6b; aqui solo
viven los casos y su formato.

Ver `docs/PLAN.md` (fase 5) y ADR 0017 (formato de resultados).

## Dos pistas

- `conformance` (determinista): casos ejecutados contra adaptadores FAKE, con
  configuracion de fixture. Salida reproducible; el `conformance_digest` es
  estable. Valida pipeline, ruteo, fallback, trazas e identidad. NO necesita
  red ni GPU.
- `smoke` (calidad): casos ejecutados contra el backend real (ADR 0013) con
  la configuracion real. NO dan veredicto reproducible; dan senal de calidad
  y latencia contra umbrales.

## Estructura de un caso

Campos comunes:

- `id`: identificador unico.
- `track`: `conformance` | `smoke`.
- `description`: que valida.
- `capability`: `prompt.run` | `domain.route` | `model.list` |
  `config.validate` | ...
- `input`: entrada de la capacidad (`prompt`, `domain`, `identity`, ...).

Solo `conformance`:

- `fixture`: ruta a la config de fixture (p.ej. `eval/fixtures/config.yaml`).
  Para casos de `config.validate`, se puede embeber `config_inline` en vez de
  `fixture` (la config bajo prueba es el propio input).
- `world` (opcional): condiciones controladas, p.ej. `unavailable_models`.
- `expect`: aserciones (`domain`, `model`, `error_type`, campos de traza...).

Solo `smoke`:

- `thresholds`: umbrales (`latency_ms_max`, `must_be_nonempty`, `min_chars`,
  `must_contain`...).

## Archivos

- `eval/fixtures/config.yaml`: configuracion de fixture (modelos/dominios
  fake) para la pista conformance. Autocontenida.
- `eval/battery/conformance.yaml`: casos deterministas.
- `eval/battery/smoke.yaml`: casos de calidad contra backend real (seed).

## Bateria v0.2: task.run (orquestacion)

`eval/battery/v0.2/orchestration.yaml` + `eval/fixtures/orchestration.yaml`
fijan el criterio de aceptacion de `task.run` (ADR 0036) ANTES de implementarlo
(fase v0.2-2). Vive en el subdirectorio `v0.2/` porque el runner solo carga
`eval/battery/*.yaml` (no recursivo); en la fase v0.2-3 el runner lo incorpora
y el `conformance_digest` se recalcula (cambio declarado, ADR 0017).

Digest historico v0.2, declarado tras incorporar los 13 casos de orquestacion
(23 casos de conformidad totales; incluye la enmienda aprobada
`task_subtask_unknown_hint`, 2026-07-16):
`1d405c95660947206a0be19a6f8ef8ecf92874a7718f3dd10348ab0fb040263b`.
Los dos casos `smoke` v0.2 quedan excluidos de esta ejecucion y del digest.

Scripting determinista adicional en `world.script` (lo realiza
`ScriptedFakeAdapter` en la implementacion):

- `plans`: planes que devuelve el fake planner, en orden (uno por
  re-planificacion); cada plan es una lista de subtareas
  `{prompt, domain?, domain_hint?, depends_on?}`. `domain` fija el dominio;
  `domain_hint` solo aporta contexto asesor al router semantico.
- `responses`: respuesta fija por modelo fake (workers y combiner).
- `evaluate_decisions`: decision de EVALUATE por iteracion (`done | rerun |
  replan`).
- `simulated`: agotamiento simulado (`elapsed_s`, `context_tokens`) para los
  cortes de tiempo/contexto sin reloj real.

Asserts nuevos en `expect`: `stop_reason`, `subtasks` (arbol: dominio/modelo/
sustitucion por subtarea), `checkpoints` (secuencia ordenada),
`checkpoint_counts`, `subtask_trace_fields`, `subtask_traces_share_task_id`,
`subtask_traces_link_parent`.

## Bateria v0.3 (coverage)

La pista `conformance` de coverage vive en
`eval/battery/v0.3/coverage.yaml` y usa la fixture
`eval/fixtures/orchestration_coverage.yaml`. Desde la fase v0.3-2 el runner
integra sus 11 casos.

Digest historico de conformidad v0.3 declarado tras la integracion (34 casos
de conformidad totales):
`5aa67516fb10c2a9b1040798262bc09231467f5bff02fe748a1f8b636ddd3475`.
El caso `smoke` v0.3 queda excluido del digest, como los smoke v0.2.

Digest de conformidad v0.3 declarado tras la ficha 0004 (34 casos de
conformidad totales; separador de ensamblado coverage):
`34122194cb09133eb2567093c4715d3b8c3db0c1b54a5fc147192875574a2e75`.

Digest de conformidad v0.3 declarado tras la ficha 0008 (34 casos de
conformidad totales; el caso pipeline `rerun` aserta el campo aditivo
`iteration` en sus subtareas):
`eb0113e69fdc9fc4674332995afc8950a8acc165bcc65cfa26bec4ed7d02f3c4`.

## Bateria v0.4: catalogo de capacidades

`eval/battery/v0.4/capability.yaml` fija el criterio de aceptacion de
`capability.list` (ADR 0046). Se escribio y congelo antes de implementar, y se
integro en la fase v0.4-A3 quitando el sufijo `.frozen`.

Casos congelados e invariante de cada uno:

- `capability_catalog_exact_ordered_names`: los 15 nombres exactos, ordenados
  por `name` ascendente.
- `capability_catalog_lists_itself`: `capability.list` aparece en su salida.
- `capability_catalog_prompt_run_complete_entry`: los ocho campos y valores
  exactos de la entrada completa de `prompt.run`.
- `capability_catalog_model_pull_declares_rest_mcp_gaps`: `model.pull` declara
  `rest` y `mcp` nulos, y conserva su proyeccion CLI.
- `capability_catalog_prompt_stream_declares_mcp_gap`: `prompt.stream` declara
  `mcp` nulo y conserva su proyeccion REST.
- `capability_catalog_task_run_stream_split`: `task.run` es bloqueante en
  `/task/run` y `task.stream` es streaming en `/task/stream`.
- `capability_catalog_runtime_health_cli_alias`: `runtime.health` declara
  `detect` como alias CLI.
- `capability_catalog_exact_identity_set`: solo `domain.route`, `prompt.run`,
  `prompt.stream`, `reasoning.run`, `reasoning.stream`, `task.run` y
  `task.stream` transportan identidad.
- `capability_catalog_task_run_mode_and_effort_params`: `mode` y `effort`
  declaran sus `choices` y valores por defecto.

La comparacion de `core_version` con la version de `pyproject.toml` requiere
leer otro artefacto y no es expresable en la bateria declarativa vigente. Se
declara abajo como test pytest requerido en vez de forzar el formato.

El digest se recalcula y se DECLARA al integrar la bateria en la fase v0.4-A3,
no durante su congelacion (ADR 0017).

Tests pytest requeridos para v0.4-A3, por no ser expresables en la bateria
declarativa:

- `core_version` de `capability.list` coincide con la version declarada en
  `pyproject.toml`.
- La tabla de rutas REST construida coincide con el catalogo en ruta y metodo.
- Los subcomandos del parser CLI construido coinciden con el catalogo en grupo,
  accion y alias.
- Los nombres y las firmas de las herramientas MCP coinciden con el catalogo;
  este es el gate de asercion de ADR 0046 que impide la deriva.
- `POST /task/run` devuelve JSON y `POST /task/stream` devuelve SSE, con el
  mismo contenido final.
- `runtime.health` declara el mismo `core_version` que `capability.list`.

Digest de conformidad declarado tras integrar los 9 casos de `capability.list`
(90 casos de conformidad totales), ya con la correccion de identidad de los dos
casos `stream` (ver abajo):
`a60aa35b31acff2e9e286b6fc3b8c15b4293ce3331728b0f26aabe0234eb14b8`.

Correccion de reconciliacion (2026-08-14): el caso de identidad se congelo
declarando cinco capacidades, y son SIETE: `prompt.stream` y `reasoning.stream`
transportan identidad igual que sus hermanas bloqueantes -la aceptan por REST y
por CLI-. El error venia del brief de la fase A2, que se contradecia entre su
tabla y su enunciado; el catalogo lo heredo. Corregido en la bateria y en el
catalogo antes de commitear.

## Bateria v0.4: plan explicito

`eval/battery/v0.4/plan.yaml` fija el criterio de aceptacion de
`task.plan` y de la entrada opcional `plan` de `task.run` (core ADR 0040,
0047 y 0048). Esta integrada en el runner desde la fase v0.4-B3.

Casos congelados e invariante de cada uno:

- `plan_explicit_task_plan_returns_executable_shape`: `task.plan` devuelve
  `plan`, `requirements`, `effort` y parametros efectivos; resuelve el dominio,
  invierte `covers` a `requirements[].covered_by` y no publica `covers`.
- `plan_explicit_task_plan_honors_effort`: el esfuerzo explicito gobierna el
  plan y se refleja en el resultado.
- `plan_explicit_supplied_plan_executes_directly`: un plan valido entra en
  fan-out y `plan_ready` declara `plan_source=supplied`.
- `plan_explicit_supplied_plan_has_zero_plan_attempts`: un plan suministrado no
  cuenta derivaciones: `plan_attempts=0`.
- `plan_explicit_without_plan_preserves_current_output`: sin plan de entrada se
  conserva el camino actual y `plan_source=planner`.
- `plan_explicit_supplied_plan_invalid_shape`: una forma invalida produce
  `PlanParseError`.
- `plan_explicit_supplied_plan_cycle`: un ciclo produce
  `PlanDependencyError`.
- `plan_explicit_supplied_plan_exceeds_default_limit`: el plan que supera el
  `max_subtasks` efectivo corta con ese motivo.
- `plan_explicit_supplied_plan_replan_unavailable`: `replan` sobre plan
  suministrado corta con `replan_unavailable` y conserva lo producido.
- `plan_explicit_supplied_plan_rerun_available`: `rerun` reejecuta el mismo
  plan suministrado.
- `plan_explicit_complete_echo_checks_coverage`: el echo hermano de `plan`,
  `requirements` y `effort` comprueba cobertura mediante `covered_by`, sin
  degradacion.
- `plan_explicit_without_requirements_declares_degradation`: omitir requisitos
  declara `requirements_unavailable`, marca cobertura falsa y no corta.
- `plan_explicit_without_effort_uses_default`: omitir esfuerzo aplica
  `default_effort`; no existe herencia desde el plan.
- `plan_explicit_explicit_effort_limits_supplied_plan`: el esfuerzo explicito
  manda y puede hacer que el plan recibido corte por `max_subtasks`.
- `plan_explicit_supplied_plan_budget_grant`: el plan recibido concede una vez
  `base + per_subtask * n`.
- `plan_explicit_planner_source_publishes_inverted_coverage`: la via derivada
  tambien publica requisitos con `covered_by` y plan sin `covers`; la forma no
  depende de la procedencia.

Digest de conformidad declarado tras integrar los 16 casos del plan explicito
(106 casos de conformidad totales):
`889c068d4d3cf663cf94302f382d76a9f015d5ac6876598f6fe4d11f9c221b0b`.

Ese digest incorpora tambien la entrada de `task.plan` en los dos casos del
catalogo que asertan la lista EXACTA de capacidades y el conjunto EXACTO de las
que transportan identidad.

**Que esos dos casos se muevan al anadir una capacidad es intencionado, no un
estorbo.** Se escribieron exactos a proposito: que aparezca o desaparezca una
capacidad publica del core tiene que ser un hecho declarado y visible en el
digest, no algo que se cuele. Si algun dia molesta, la respuesta NO es relajarlos
a "contiene estas": es declarar el digest nuevo, que es una linea.

Tests pytest requeridos para v0.4-B3, por no ser expresables en la bateria
declarativa vigente:

- `task.plan` no llama a ningun modelo de ejecucion, ni a COMBINE ni EVALUATE.
- `task.run` con plan suministrado no llama al planificador; se comprueba con
  un adaptador que fallaria ante cualquier llamada.
- Paridad de `task.plan` por CLI, REST y MCP: `ianest task plan`,
  `POST /task/plan` y herramienta MCP.
- Paridad de los campos hermanos `plan`, `requirements` y `effort` en
  `POST /task/run` y en la herramienta MCP de `task.run`.
- La CLI recibe el plan por FICHERO, no como argumento JSON de linea de
  comandos, y transporta tambien `requirements` y `effort`.

## Bateria del router semantico (fases 3a y 3b-i)

`eval/battery/router/domain_route.yaml` integra los 4 casos de
`domain.route` del router semantico (ADR 0043) y los 5 casos de `prompt.run` y
`task.run` de la fase 3b-i.

Digest de conformidad declarado tras integrar los 4 casos (38 casos de
conformidad totales):
`42146c0cfe52f5a1ab8f290173458fa1f28b8b5d90e6a0a101d8e282369f0226`.

Digest de conformidad declarado tras integrar los 5 casos de `prompt.run` y
`task.run` de la fase 3b-i (43 casos de conformidad totales):
`e3ea47ed3d1e30d8de9dd1b5c01fcad28fff2e7a858c3e60ef871ab7583ea13e`.

Digest de conformidad declarado tras retirar el modo keyword (fase 3b-ii):
42 casos totales. Los casos de orquestacion y coverage fijan `domain`; el caso
historico de hint desconocido pasa a la bateria del router como hint asesor, y
los dos casos keyword salen de `conformance.yaml`:
`6dcae1a56c4cb5519a86e766597f245d0e73b55fe3b86983298de5901b4e9708`.

Tests pytest requeridos para los aspectos no expresables end-to-end por la
bateria declarativa:

- Caso 3: el prompt de la llamada siguiente contiene solo unidades pendientes
  y no el texto integro aceptado.
- Caso 7: un fallo reintenta solo la unidad afectada.
- Caso 8: unidades independientes respetan `max_parallel`.
- Caso 12: streaming y bloqueante producen el mismo contenido final.
- Caso 13: la telemetria JSONL reconstruye cobertura, fragmentos y modelos.
- Caso 14: los casos 1-13 usan solo adaptadores fake.

Caso 15, smoke real: declarar y verificar `coverage_complete=true` y
`chunk_index >= 2`, sin exigir texto exacto.

## Bateria de invariantes del orquestador (ADR 0041)

`eval/battery/v0.3/invariantes_orquestador.yaml`: 19 casos de
conformidad para los CUATRO invariantes del ADR 0041 (adecuacion semantica,
negociacion de presupuesto, cortes no silenciosos y degradacion declarada), en
los dos modos de `task.run`. Se escribio y congelo ANTES de implementar; ya esta
integrada y el runner la carga.

Historia de la bateria, porque explica su forma:

- Congelada el 2026-08-06 con 10 casos para I1, I2 e I3.
- Reconciliada con ADR 0043 el 2026-08-11: se congelo ANTES del router
  semantico, y sus subtareas y unidades declaraban solo `domain_hint`, que bajo
  aquel ADR dejo de decidir. Como estos fixtures no configuran router, los casos
  habrian muerto con `RoutingError`. Ahora fijan `domain`, igual que las
  baterias ya integradas. La semantica ASESORA del hint se prueba en la bateria
  del router: aqui el clasificador no debe ser una variable.
- Ampliada el 2026-08-11 con 8 casos para I4. Aportan una primitiva de guion
  nueva, `derivations: [{ raw: "<texto>" }]`, que hace que el fake
  planificador devuelva ese texto literal: I4 se prueba contra salidas
  MALFORMADAS y el guion estructurado solo sabe emitir planes bien formados.
- Ampliada el 2026-08-11 con un caso de observabilidad: `plan_ready` cuenta las
  derivaciones (incluida una re-planificacion), no las vueltas por `rerun`.

Digest de conformidad declarado tras implementar ADR 0044 (61 casos totales, sin
cambio de recuento): el corte por presupuesto de `task.run` pasa a llamarse
`max_total_tokens` en los DOS modos, y los limites retirados
-`orchestration.max_context_tokens` y `coverage.max_total_tokens`- dejan de
publicarse como parametros efectivos y los sustituye `token_budget_total`, la
concesion calculada. Se movieron exactamente tres casos ya integrados:
`task_stop_max_context` (renombra su corte), `coverage_stop_max_total_tokens` y
`coverage_ten_units_three_per_chunk` (sustituyen el limite por la concesion).
`reasoning_max_context_tokens` NO cambia: `reasoning.run` conserva su corte con
ese nombre, que es otro concepto (ADR 0008):
`bf3fcc47920c05b8dee03490acca8bf41b1999ba81d9d3a4806e77f45c360d13`.

Digest de conformidad declarado tras integrar los 19 casos del ADR 0041 (61
casos totales: los 42 anteriores, sin cambio de resultado, mas los 19 nuevos).
El cambio de digest incorpora I1-I4, los contadores independientes de PLAN y
EVALUATE, la degradacion declarada y la semantica de `plan_ready` por
derivacion:
`4fb027834bda6ae4c51567ff9c931afa5967402de85613287def983981ac9563`.

Tests pytest requeridos, por no ser expresables end-to-end en la bateria
declarativa:

- La comprobacion de I1 no genera NINGUNA llamada de modelo adicional:
  `requirements` y unidades llegan en la misma respuesta del planificador.
- La instruccion de re-derivacion nombra los requisitos huerfanos (I1) y el
  presupuesto disponible (I2) en el texto del prompt.
- I3 en la CLI: un corte por limite termina con codigo de salida distinto de
  cero y explica el motivo por stderr, en los dos modos.
- I4 en EVALUATE: decision ilegible corregida al renegociar; ilegible dos veces
  que asume `done` y lo declara; independencia respecto al contador de PLAN; y
  camino sano con una sola evaluacion.
- Una degradacion se avisa por stderr sin cambiar el codigo de salida cero.
- Paridad: `requirements_covered` y `uncovered_requirements` viajan por
  CLI (`--json`), REST y MCP, junto a `plan_attempts`, `evaluation_attempts` y
  `degradations`.

Smoke real pendiente de laboratorio: el prompt de los ocho planetas
(`enumera los ocho planetas ... y explica brevemente cada uno`) debe terminar
con `requirements_covered=true` y una respuesta que incluya descripciones.
Es el caso que motivo el ADR y su regresion natural.

### Decision D-AUSENCIA

El caso `invariantes_planificador_no_declara_requisitos` fija que un
planificador que omite `requirements` se trata como si dejase todos los
requisitos huerfanos (ADR 0041, decision `D-AUSENCIA`, reconciliada
2026-08-06). Si el comportamiento no convence en uso, esa etiqueta localiza la
decision, su motivo y las dos alternativas descartadas.

## Convenciones

Claves en ingles snake_case (ADR 0016). El esquema de config sigue el ADR
0014; el de traza, el ADR 0015.

## Bateria de presupuesto y esfuerzo (ADR 0044 y 0045)

`eval/battery/v0.3/presupuesto_y_esfuerzo.yaml`: 20 casos de conformidad
-9 del presupuesto dimensionado por el plan (ADR 0044) y 11 de los niveles de
esfuerzo (ADR 0045)-, sobre las fixtures
`eval/fixtures/orchestration_effort.yaml` y su variante
`..._default_low.yaml`. Escrita y CONGELADA antes de implementar, e integrada
tras implementar ambas decisiones.

Las fixtures declaran `token_budget`, `effort` y `default_effort`. Durante la
congelacion fueron claves inertes; ahora el esquema, el cargador y el runtime
las consumen.

**Esta bateria fija SEMANTICA, no calibracion.** Sus numeros son redondos
-`base: 1000`, `per_subtask: 500`- para que cada caso se lea de un
vistazo. Los valores que se publiquen en esquema, cargador y plantillas salen de
la puerta de laboratorio (ADR 0044 D5 y ADR 0045 D7) y son otra cosa: cambiarlos
alli no debe tocar esta bateria.

Dos casos son guardas contra regresiones de diseno, no contra regresiones de
codigo, y conviene no borrarlos aunque parezcan redundantes:

- `esfuerzo_no_toca_los_ejes_de_maquina`: `max_parallel`, `units_per_chunk` y
  `max_no_progress_iterations` no cambian con el nivel. Son forma del
  despliegue, territorio de `pulse` (ADR 0037), no ganas de trabajar.
- `esfuerzo_no_toca_la_medicion_del_coste`: para el mismo `n`, el
  `token_budget` resuelto es identico en los tres niveles. Sin esta guarda,
  alguien reintroduce el multiplicador sobre `per_subtask` -que es la lectura
  intuitiva de "nivel de esfuerzo" y la que traia el primer borrador del ADR- y
  nadie se entera.

Digest de conformidad declarado tras integrar ADR 0044 y ADR 0045 (81 casos
totales: los 61 anteriores, sin regresiones, mas los 20 casos de presupuesto y
esfuerzo):
`6b7067efb290b135562a656e0406f26a4a06d5e4cb9be13fb5aaf05c44be678a`.

## Bateria de la GPU del backend (ADR 0049, linea de observacion del backend)

`eval/battery/v0.4/backend_gpu.yaml`: 11 casos de conformidad, escritos y
CONGELADOS en la fase 2 e integrados en la fase 3.

Fixtures propias: `eval/fixtures/backend_gpu.yaml` (dos modelos ollama sobre UN
endpoint) y `eval/fixtures/backend_gpu_dos_endpoints.yaml` (dos endpoints
distintos). Ninguno de esos endpoints existe: la sonda va guionizada desde el
caso y no toca red. El tercer proveedor lo aporta `eval/fixtures/config.yaml`,
cuyo `provider: fake` no tiene sonda y sirve para el caso de degradacion.

**Regla de diseno**: los casos guionizan lo que devuelve el BACKEND -por modelo
cargado, `size` y `size_vram`- y esperan el `status` DERIVADO. Un caso que
guionizase el `status` no probaria nada, porque la regla ES la comparacion. Las
cifras salen de la verificacion real contra ollama 0.12.2, no son inventadas.

Cubre los cuatro estados (`in_use`, `partial`, `cpu_only`, `unknown`), las tres
causas de `unknown` (`no_models_loaded`, `backend_unreachable`,
`provider_unsupported`), la regla de agregacion cuando un endpoint tiene varios
modelos cargados, la separacion en dos entradas con dos endpoints, el orden
determinista y la invariante de que `runtime.health` nunca falla por la sonda.

Dos casos son guardas de diseno y conviene no borrarlos aunque parezcan
redundantes:

- `backend_gpu_partial`: es el estado que la comprobacion `size_vram == 0` del
  prototipo NO veia, y el mas probable con una sola tarjeta y varios dominios.
  Sin esta guarda, alguien vuelve a la comparacion binaria y el fallo caro
  -mayoria de capas en el procesador reportada como `in_use`- vuelve a ser
  invisible.
- `backend_gpu_orden_determinista`: la fixture declara `ollama_dos` ANTES que
  `ollama_uno` a proposito. Si la implementacion devolviera las entradas en
  orden de declaracion en vez de ordenadas, el digest bailaria entre ejecuciones
  y este caso lo destapa.

Tests pytest requeridos para la fase 3, por no ser expresables en la bateria
declarativa:

- Ninguna entrada de `backend.gpu` contiene la URL del endpoint, ni como valor
  ni como clave. Es la propiedad que justifica identificar por `id` de modelo:
  `runtime.health` no tiene autenticacion y no debe publicar la topologia
  interna.
- `gpu` (runtime LOCAL) y `backend.gpu` son independientes: con la deteccion
  local sustituida por una que declara `available: false`, una entrada de
  `backend.gpu` puede valer `in_use` a la vez. Es la prueba de que los dos
  campos dicen cosas distintas y las dos ciertas, y es el gate de laboratorio de
  la fase 3 expresado en conformidad.
- La sonda NO se ejecuta en el camino de inferencia: `prompt.run` y `task.run`
  no la invocan ni una vez, verificado con una sonda que fallaria si la llamasen.
- Paridad CLI/REST/MCP del campo, derivada del catalogo y no escrita a mano.
- `runtime.detect` publica el mismo `backend.gpu` que `runtime.health`, por
  compartir implementacion.

Digest de conformidad declarado tras integrar los 11 casos de la GPU del
backend (117 casos de conformidad totales). Los 106 casos anteriores conservan
exactamente el digest declarado `889c068d...`; solo se anaden los 11 casos que
asertan la aparicion de `backend.gpu` en el payload publico de
`runtime.health`:
`b4fb435089372d4df0b722dc90f1b781984ff90e375d7c0e907142e054676594`.
