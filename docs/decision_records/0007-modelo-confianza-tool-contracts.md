# Decision 0007: modelo de confianza de tool_contracts, denegar por defecto

Fecha: 2026-07-10

## Decision

Ninguna herramienta tiene acceso implicito a shell, filesystem o red. Cada
herramienta declara capacidades y ambito (scopes) explicitos; el core
aplica allowlist. Toda operacion marcada como destructiva o irreversible
exige confirmacion humana (human-in-the-loop) y no puede ejecutarse en modo
desatendido.

## Motivo

Traduce el no-objetivo "no automatizacion Linux destructiva" a una regla
tecnica exigible, y mitiga tool poisoning / confused deputy conocidos en el
ecosistema MCP.

## Consecuencia

`tool_contracts` implementa allowlist y confirmacion; denegar por defecto es
el estado base. Detalle en `ARCHITECTURE.md` (D5).
