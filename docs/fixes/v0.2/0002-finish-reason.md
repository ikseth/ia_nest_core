# 0002: exponer finish_reason (senal de truncado)

Estado: propuesta
Tipo: mejora compatible
Impacto de version: patch
Version objetivo: v0.2.x

## Problema

El adaptador OpenAI-compatible lee el texto de la respuesta pero IGNORA el
campo `finish_reason` de cada choice. El core no puede distinguir una respuesta
terminada de forma natural (`stop`) de una truncada por limite de tokens
(`length`). Sin esa senal, ni el usuario lo sabe de forma programatica ni la
futura capa `pulse` (ADR 0037) puede regular los limites por dominio a partir
del historico de truncados.

## Cambio

Capturar `finish_reason` en el adaptador y propagarlo como senal observable,
sin editorializar (el core transporta el valor crudo del backend; interpretar
`length` como "truncado" es cosa de los consumidores).

- `openai_compatible`: leer `choice.get("finish_reason")` del stream y quedarse
  con el ultimo valor no nulo.
- `fake` / `ScriptedFakeAdapter`: emitir un `finish_reason` DETERMINISTA (por
  defecto `stop`; scriptable a `length` para pruebas de truncado).
- Evento `done` (adapters/base): incorporar `finish_reason` a su payload; el
  helper `run_blocking` lo conserva.
- `prompt.run`: incluir `finish_reason` en la traza (`PromptRunResult.trace`) y
  en el payload JSONL del evento `done`.
- `task.run`: incluir `finish_reason` en el registro de cada subtarea (para que
  pulse vea el truncado por dominio/subtarea).
- `reasoning.run` (si sale limpio): `finish_reason` por paso.

Restricciones duras:

- CSV de telemetria: NO se anade columna (18 columnas congeladas, ADR 0015).
  `finish_reason` vive solo en el payload JSONL.
- Bateria congelada: NO se anaden casos de conformance (evita churn del digest
  mas alla del payload). La cobertura de esta ficha son unit tests. Si al
  incorporar `finish_reason` al payload el `conformance_digest` cambia, se
  RECALCULA y se declara (test + `eval/README.md`, ADR 0017); si no cambia, se
  deja igual.

## Criterios de aceptacion

- El adaptador OpenAI-compatible surface `finish_reason` en el evento `done`.
- Un `ScriptedFakeAdapter` con `finish_reason=length` lo propaga hasta la traza
  de `prompt.run` y hasta el registro de subtarea de `task.run`.
- `finish_reason` aparece en el JSONL; el CSV conserva exactamente 18 columnas.
- pytest en verde con y sin extras. Si el digest cambia, queda declarado.
- Core minimo instalable; sin dependencias nuevas.

## Archivos previstos

- `src/ianest_core/adapters/openai_compatible.py`
- `src/ianest_core/adapters/fake.py`
- `src/ianest_core/adapters/base.py`
- `src/ianest_core/runtime/prompt_runtime.py`
- `src/ianest_core/runtime/task_runtime.py`
- `src/ianest_core/runtime/reasoning_runtime.py` (si sale limpio)
- `tests/` (unit tests nuevos)
- `eval/README.md` y `tests/test_phase_6b.py` (solo si el digest cambia)
- `CHANGELOG.md`

## Resultado

(pendiente)
