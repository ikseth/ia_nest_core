# Decision 0006: version de protocolo MCP declarada y verificable

Fecha: 2026-07-10

## Decision

El core declara una version objetivo del protocolo MCP en `runtime.health` y
la hace verificable (un cliente puede comprobar contra que version habla).
Se soporta salida estructurada de herramientas. El numero de version
concreto se elige al implementar la interfaz MCP.

## Motivo

Evitar incompatibilidad futura por revisiones del protocolo (auth,
elicitation, salidas estructuradas), sin anclar en el borrador un numero de
version que quede obsoleto.

## Consecuencia

El compromiso es que exista una version declarada y verificable, no que el
numero este ya elegido. Se fija el numero exacto al implementar, tras
verificar la revision estable vigente entonces. Detalle en `ARCHITECTURE.md`
(D4).

## Estado (cerrado en fase 7, 2026-07-11)

`runtime.health` declara la version leyendola dinamicamente del SDK oficial
`mcp` (`mcp.types.DEFAULT_NEGOTIATED_VERSION`), con `2025-03-26` como
fallback cuando el extra no esta instalado.

- Con `mcp` 1.28.1: version declarada `2025-03-26` (el `LATEST_PROTOCOL_VERSION`
  del SDK es `2025-11-25`; se declara la negociada por defecto, mas
  conservadora).
- Verificado por Opus: el valor coincide con el del SDK y `runtime.health` lo
  expone por CLI/REST/MCP.
