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

## Convenciones

Claves en ingles snake_case (ADR 0016). El esquema de config sigue el ADR
0014; el de traza, el ADR 0015.
