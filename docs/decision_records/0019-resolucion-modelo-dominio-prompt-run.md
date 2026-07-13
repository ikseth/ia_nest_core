# Decision 0019: resolucion de modelo/dominio en prompt.run

Fecha: 2026-07-11

## Decision

`prompt.run` resuelve el modelo con precedencia explicita:

1. Modelo directo declarado -> se usa ese modelo (bypass del orquestador).
2. Dominio declarado -> se usa `domains[].preferred_model` del dominio.
3. Nada declarado -> el orquestador/router decide (fase 6b) o el dominio por
   defecto `general` (fase 6a).

El modelo resuelto debe existir en `models[]` (config/registry, ADR 0014).

## Motivo

Encaja con la vision de IA_NEST como estructura de piezas configurables y
opcionales: un orquestador principal mas la capacidad de declarar modelos
directos, con modelos descargables y seleccionables por el usuario. La
precedencia explicita evita ambiguedad.

## Consecuencia

- Fase 6a implementa las dos vias explicitas (modelo directo, dominio); la
  via auto-route es fase 6b.
- Se refleja en `CORE_CONTRACT.md` (`prompt.run`).
- Los modelos seleccionables se declaran en config (ADR 0014); descargarlos
  es tarea del backend (ADR 0013), no del core.
