# Decision 0018: interfaz ModelAdapter (streaming-first)

Fecha: 2026-07-11

## Decision

`ModelAdapter` expone un unico metodo `stream(req) -> Iterator[Event]`. El
modo bloqueante NO es un metodo del adaptador: es un helper compartido
`run_blocking(adapter, req) -> ModelResponse` que colecta el flujo hasta
`done`.

Formas:

- `Event = {type: token | step | trace | done | error, data}` (eventos D2,
  ADR 0004).
- `ModelRequest = {messages, params, extra}` (`params` del perfil; `extra`
  opaco, ADR 0003).
- `ModelResponse = {text, model, tokens_in, tokens_out}`.

## Motivo

Coherente con ADR 0004 (streaming como primitiva). Un solo camino de codigo
evita que bloqueante y streaming diverjan, y el helper bloqueante no se
duplica en cada adaptador. Es la costura de intercambiabilidad de modelos
(D1), asi que su forma se fija explicitamente y no se infiere.

## Consecuencia

- `OpenAICompatibleAdapter` y `FakeAdapter` implementan solo `stream()`.
- La forma de `Event`/`ModelRequest`/`ModelResponse` es contrato interno;
  cambiarla exige decision registrada.
