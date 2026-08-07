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
  `{prompt, domain_hint?, depends_on?}`.
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

`eval/battery/v0.3/invariantes_orquestador.yaml.frozen`: 10 casos de
conformidad para los tres invariantes del ADR 0041 (adecuacion semantica,
negociacion de presupuesto y cortes no silenciosos), en los dos modos de
`task.run`. Congelada ANTES de implementar; el runner no la carga mientras
conserve el sufijo `.frozen`.

Al integrarla (rename a `.yaml`) el digest se recalcula y se DECLARA, con el
patron de v0.2-3 y v0.3-2. El digest cambia ademas por la ficha v0.3/0004
(separador en el ensamblado), que altera el `response` esperado de ocho casos
de `coverage.yaml`. Ambos cambios son intencionados y estan declarados por
adelantado; el digest historico de 34 casos queda arriba.

Tests pytest requeridos, por no ser expresables end-to-end en la bateria
declarativa:

- La comprobacion de I1 no genera NINGUNA llamada de modelo adicional:
  `requirements` y unidades llegan en la misma respuesta del planificador.
- La instruccion de re-derivacion nombra los requisitos huerfanos (I1) y el
  presupuesto disponible (I2) en el texto del prompt.
- I3 en la CLI: un corte por limite termina con codigo de salida distinto de
  cero y explica el motivo por stderr, en los dos modos.
- Paridad: `requirements_covered` y `uncovered_requirements` viajan por
  CLI (`--json`), REST y MCP.

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
