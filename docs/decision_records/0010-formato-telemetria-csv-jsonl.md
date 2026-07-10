# Decision 0010: formato de telemetria CSV clasico + JSONL, sin sqlite

Fecha: 2026-07-10

## Decision

Nada de sqlite. La telemetria se persiste en dos sinks de formato fijo y
documentado:

- CSV para telemetria clasica tabular: latencia, tokens, modelo, dominio,
  veredicto, identidad, timestamps. Delimitador ";". Rotacion por tamano
  y/o fecha. Esquema (orden y nombres de columna) congelado y versionado.
  El CSV NO contiene cuerpos de prompt ni de respuesta.
- JSONL (un objeto JSON por linea) para todo lo que involucre contenido de
  prompt o respuesta, y para eventos estructurados o anidados.

## Motivo

Formato estandar, legible, rotable y sin dependencia de motor de base de
datos. Separar contenido (JSONL) de metrica tabular (CSV) evita de raiz el
problema de delimitadores y saltos de linea en texto libre.

## Consecuencia

- El texto libre vive siempre en JSONL, nunca en el CSV. Para cualquier
  campo CSV se usa la libreria CSV estandar del lenguaje, no un parser
  propio.
- Regla de resiliencia: un fallo de telemetria NO debe romper la inferencia.
  La escritura es best-effort y se degrada en silencio (con su propio
  registro de error), salvo un modo estricto opt-in.
- Cambiar el esquema exige decision registrada. Detalle en `ARCHITECTURE.md`
  (D8).
