# Decision 0002: registrar riesgos de diseno de una revision cruzada

Fecha: 2026-07-10

## Decision

Registrar formalmente, en `docs/ARCHITECTURE.md`, los riesgos de diseno
detectados en una revision cruzada realizada por Claude Code (metodo
steelman) a peticion del usuario, en vez de dejarlos solo en el historial
de conversacion.

## Motivo

El repo se trabaja con mas de una IA (ver seccion "Colaboracion entre
varias IA" en `IA_NEST_CORE_CONTEXT.md`). Una IA distinta a la que genero
el hallazgo no tiene acceso a esta conversacion, por lo que el hallazgo se
perderia si no queda escrito en un documento del repo.

## Consecuencia

Los siguientes puntos quedan pendientes de resolver, cada uno mediante su
propio ADR, antes de implementar el componente que afectan:

- protocolo de cable del runtime de inferencia,
- soporte de streaming en `prompt.run` / `reasoning.run`,
- politica de fallo ante modelo no disponible,
- version de protocolo MCP objetivo,
- modelo de confianza/sandboxing para `tool_contracts`,
- presupuesto de contexto/tokens en `reasoning_loop`.

Ninguno de estos puntos cambia el alcance actual del core; son huecos de
detalle dentro del alcance ya definido en `docs/ALCANCE_CORE.md`.
