# Decision 0015: esquema de traza de telemetria

Fecha: 2026-07-10

Concreta el formato fijado en el ADR 0010 (CSV clasico + JSONL), definiendo
columnas y campos. Congelado y versionado (`schema_version`).

## Decision

Dos sinks correlacionados por `request_id`.

CSV (metrica tabular, delimitador ";", sin cuerpos de prompt/respuesta), una
fila por evento. Columnas en orden fijo:

1. `schema_version`
2. `ts` (ISO 8601)
3. `request_id`
4. `event` (`request_start` | `route` | `model_call` | `step` | `milestone` |
   `done` | `error`; ver correspondencia con D2 mas abajo)
5. `capability` (`prompt.run` | `reasoning.run` | `domain.route` | ...)
6. `user_id`
7. `service`
8. `session_id`
9. `domain_tag`
10. `namespace`
11. `domain` (seleccionado)
12. `model` (usado)
13. `latency_ms`
14. `tokens_in`
15. `tokens_out`
16. `verdict` (evaluacion; vacio si no aplica)
17. `status` (`ok` | `error`)
18. `error_type` (vacio si `ok`)

Los campos de identidad (6-10) pueden ir vacios en capacidades
administrativas (ADR 0011). Se usa la libreria CSV estandar del lenguaje.

JSONL (contenido; un objeto JSON por linea) para prompts, respuestas, pasos
de razonamiento, llamadas a herramienta y detalle de hito. Campos:

- `schema_version`, `ts`, `request_id`, `event`, `capability`,
- identidad (`user_id`, `service`, `session_id`, `domain_tag`, `namespace`),
- `payload` (estructurado/anidado: el contenido).

## Correspondencia con los eventos de stream (D2)

La arquitectura D2 define un flujo de eventos de ejecucion: `token`, `step`,
`trace`, `done`, `error`. La telemetria observa ese flujo y lo persiste asi:

- `token`: NO se escribe al CSV (es un delta de streaming de alta
  frecuencia). Su contenido agregado (respuesta completa) va a JSONL en
  `done`; su recuento alimenta `tokens_out` en la fila CSV.
- `step`: fila CSV de tipo `step` + `payload` en JSONL con el detalle.
- `trace`: anotacion interna; va a JSONL (y a CSV si marca un hito de ciclo).
- `done` / `error`: fila CSV de cierre + `payload` en JSONL (respuesta o
  error).

Los tipos `request_start`, `route`, `model_call` y `milestone` son marcadores
de telemetria generados por el core (no eventos de stream D2): inicio de
request, decision de ruteo, llamada al backend y senal de hito de memoria
(ADR 0008/0011).

## Motivo

Da un esquema concreto y estable para que la fase 6a emita trazas sin inferir
formato, y para que traza y memoria compartan identidad (ADR 0011).

## Consecuencia

- El texto libre vive solo en JSONL, nunca en CSV (ADR 0010).
- Un fallo de escritura de traza no rompe la inferencia salvo `strict_mode`
  (ADR 0010).
- Cambiar columnas o campos incrementa `schema_version` y exige decision
  registrada.
