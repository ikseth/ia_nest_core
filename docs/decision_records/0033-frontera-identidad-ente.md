# Decision 0033: frontera de identidad del ente (pack basico)

Fecha: 2026-07-16

## Decision

IA_NEST define un ENTE con identidad propia (simulada), formado por el "pack
basico" de cuatro piezas:

- `ia_nest_core`: el motor (enruta, infiere, itera).
- `ia_nest_core_extended`: la memoria/conocimiento (enriquecimiento: RAG,
  memoria, datos web).
- `ia_nest_core_conscience`: la mente supervisora (control etico/personalidad,
  ADR 0034).
- `ia_nest_web`: la cara (GUI de gestion y de usuario).

Todo lo demas es EXTERIOR y se conecta al ente por sus contratos publicos:
agentes (`ia_nest_agents`), integraciones (`ia_nest_external_*`), modulos
(`ia_nest_module_*`), monitorizacion (`ia_nest_core_ops`, que observa el ente
desde fuera) y, en el futuro, OTRAS entidades IA_NEST (comunicacion
entidad-a-entidad, registrada en `docs/CAPAS_FUTURAS.md`).

Regla derivada: la orquestacion del propio pensamiento pertenece al ente
(al core, ADR 0034). Ningun elemento exterior dirige como piensa el ente.

## Motivo

`VISION_FUNCIONAL.md` ya lo contenia: el core es "orquestador local de modelos
IA" y "nucleo para agentes"; los agentes "quedan fuera" y CONSUMEN por
contratos; la consciencia es "capa superior de control, evolucion y simulacion
de IA consciente". El salto que da entidad es core + memoria + conscience: la
personalidad y sabiduria (erronea o no) del ente se forman de sus experiencias
y procesos de automejora, no de un director externo. Si un agente externo
orquestara el pensar del ente, el ente seria una marioneta.

## Consecuencia

- El mapa de repos (`IA_NEST_CORE_CONTEXT.md`) y el registro de capas
  (`docs/FRONTERAS.md`) se organizan en dos zonas: ente / exterior.
- Alternativa descartada: orquestacion multi-modelo en `ia_nest_agents`
  (propuesta previa de Claude, retirada en reconciliacion).
- La comunicacion entidad-a-entidad se registra como frontera futura del ente.
