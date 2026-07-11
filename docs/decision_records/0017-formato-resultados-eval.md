# Decision 0017: formato de resultados de eval.run

Fecha: 2026-07-11

Congela el formato de salida de `eval.run` (CORE_CONTRACT), entregable de la
fase 5. Versionado por `schema_version`.

## Decision

`eval.run` devuelve un objeto con resultado por caso y un agregado.

Por caso:

- `case_id`
- `track` (`conformance` | `smoke`)
- `status` (`pass` | `fail` | `error`)
- `capability` (p.ej. `prompt.run`, `domain.route`)
- `domain` (usado), `model` (usado)
- `latency_ms`
- `assertions` (solo `conformance`): lista de
  `{ name, expected, actual, ok }`.
- `metrics` (solo `smoke`): `{ latency_ms, tokens_in, tokens_out, chars }` y
  `thresholds_met` (bool).
- `error` (si `status = error`): `{ type, message }`.

Agregado:

- `run_id`, `ts` (ISO 8601), `schema_version`
- `totals`: `{ conformance: {pass, fail}, smoke: {pass, fail} }`
- `conformance_digest`: hash reproducible sobre los resultados de la pista
  `conformance` (detecta regresiones de forma determinista).
- `verdict`: `pass` si toda la pista `conformance` pasa y la `smoke` cumple
  sus umbrales.

## Motivo

Separa determinismo (conformance, con `conformance_digest` estable) de
calidad (smoke, con umbrales). Cumple el criterio de salida de la fase 5:
formato congelado y veredicto reproducible en la pista determinista.

## Consecuencia

- El `conformance_digest` NO incluye la pista `smoke` (no es reproducible bit
  a bit; ADR 0010/0013).
- El motor que produce este formato se implementa en fase 6b (semilla de
  `eval.run`). Este ADR solo fija la forma.
- Cambiar el formato incrementa `schema_version` y exige decision registrada.
