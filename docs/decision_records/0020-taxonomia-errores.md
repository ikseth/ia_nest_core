# Decision 0020: taxonomia de errores

Fecha: 2026-07-11

## Decision

Jerarquia tipada bajo una base `CoreError`:

- `CoreError`: `type` (string estable), `message`, `field` (opcional).
- Subclases: `ModelUnavailable`, `ConfigValidationError`, `AdapterError`,
  `RoutingError` (y las que surjan).

Se serializan igual en CLI, REST y MCP: `{type, message, field}`.

## Motivo

La bateria de evaluacion referencia `error_type` y `error_field`; la paridad
de interfaces (regla de `CORE_CONTRACT.md`) exige una superficie de error
consistente y no ad-hoc.

## Consecuencia

- Los `error_type` usados en la bateria (`ModelUnavailable`,
  `ConfigValidationError`) son parte del contrato.
- Anadir nuevos tipos es libre; cambiar o renombrar un `type` existente exige
  decision registrada (rompe consumidores).
