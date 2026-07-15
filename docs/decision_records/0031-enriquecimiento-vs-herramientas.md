# Decision 0031: enriquecimiento de contexto vs herramientas (dos costuras)

Fecha: 2026-07-15

## Decision

Se distinguen DOS costuras hacia las capas externas, que hasta ahora se
mezclaban:

- **Enriquecimiento de contexto** (RAG, memoria, datos web): inyecta datos en
  el prompt antes/alrededor de la inferencia. Es SOLO LECTURA, sin efecto
  lateral. Se conecta por costura tipo `Port` (patron de `MemoryPort`, ADR 0011),
  NO por `tool_contracts`. No requiere allowlist ni human-in-the-loop.
- **Herramientas** (`tool_contracts`, ADR 0007): ejecutan ACCIONES con efecto
  (shell, filesystem, red, integraciones que actuan). Denegar por defecto,
  scopes, confirmacion humana en lo destructivo. Sigue diferido (ADR 0022)
  hasta que exista una herramienta concreta.

RAG, memoria y datos web viven en la capa de enriquecimiento
(`ia_nest_core_extended`) y NO dependen de `tool_contracts`.

## Motivo

RAG/memoria/datos-web son recursos necesarios para que el core de una respuesta
real y potente: datos actuales (web), continuidad de conversacion (memoria) y
conocimiento acotado a datos deseados (RAG). Cualquier consumidor -un chatbot o
el propio prompt- se enriquece con ellos sin "invocar" nada. Tratarlos como
herramientas les imponia el modelo de confianza de ADR 0007 (pensado para
acciones con efecto), que no les corresponde. ADR 0011 ya modela la memoria como
`Port`, no como herramienta: esta ADR generaliza ese criterio.

Precision: ADR 0022 (diferir tool_contracts) NO clasificaba RAG/web como
herramientas; la imprecision estaba en `FRONTERAS.md`, que ofrecia RAG/web
"como herramientas o como enriquecimiento". Esta ADR fija el enriquecimiento
como la via, y reserva `tool_contracts` para acciones.

## Consecuencia

- `docs/FRONTERAS.md` reescribe la linea de RAG/web: enriquecimiento como costura
  propia; `tool_contracts` solo para integraciones que actuan.
- Diseno abierto (a resolver al arrancar `ia_nest_core_extended`): si el
  enriquecimiento lo hace la capa (arma el prompt y llama a `prompt.run`, cero
  contrato nuevo en el core) o si el core expone un puerto de enriquecimiento
  (como `MemoryPort`). La memoria ya tiene su costura (ADR 0011).
- `tool_contracts` (ADR 0007/0022) queda intacto y sigue diferido, ahora acotado
  a acciones/integraciones (`ia_nest_external_*`).
