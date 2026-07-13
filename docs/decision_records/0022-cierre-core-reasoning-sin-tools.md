# Decision 0022: cierre del core - reasoning.run sin herramientas, tool_contracts diferido

Fecha: 2026-07-11

## Decision

Secuencia para cerrar el core (checklist "core cerrado" de
`IA_NEST_CORE_CONTEXT.md`):

- Fase 8: `reasoning.run` (bucle de razonamiento minimo, observable, con
  limites) SIN invocacion de herramientas.
- Fase 9: scripts de instalacion y deteccion de runtime/GPU.
- Fase 10: plan de repos/modulos externos.
- `tool_contracts` (ADR 0007): diferido, sin fase asignada, hasta que exista
  una herramienta concreta que lo justifique.

## Motivo

`reasoning.run` es capacidad del contrato y del checklist de cierre; se
implementa sin herramientas para mantener la pieza pequena y testeable.
Construir `tool_contracts` sin una herramienta real seria aceptar un modulo
por utilidad potencial, que la regla anti-entropia prohibe. Los scripts
cierran el ultimo punto pendiente de `ALCANCE_CORE.md`.

## Consecuencia

- El bucle de razonamiento se disena aparte (proximo brief), reutilizando
  `prompt_runtime`, adaptadores y telemetria; limites por perfil (ADR 0008).
- `tool_contracts` (ADR 0007) sigue siendo decision valida pero no
  planificada; se planificara cuando surja la necesidad concreta.
- `docs/PLAN.md` actualizado con las fases 8, 9 y 10.
