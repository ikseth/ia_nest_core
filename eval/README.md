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
