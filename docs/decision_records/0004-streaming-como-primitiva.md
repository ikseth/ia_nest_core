# Decision 0004: streaming como primitiva, bloqueante como conveniencia

Fecha: 2026-07-10

## Decision

El contrato interno de ejecucion emite un flujo de eventos
(`token`, `step`, `trace`, `done`, `error`). La variante bloqueante es un
consumidor que colecta el flujo hasta `done`.

## Motivo

Un solo contrato que no se rompe al anadir streaming despues. Preserva la
promesa de contratos pequenos y versionados.

## Consecuencia

REST expone SSE, CLI expone chunks, MCP streaming donde aplique; el modo
bloqueante colecta el flujo. Detalle en `ARCHITECTURE.md` (D2).
