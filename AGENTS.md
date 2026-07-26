# Instrucciones para agentes de IA en este repo

Antes de proponer o valorar cualquier cambio de diseno, lee en este orden:

1. `IA_NEST_CORE_CONTEXT.md`
2. `docs/VISION_FUNCIONAL.md`
3. `docs/LINEA_DE_ACTUACION.md`
4. `docs/ALCANCE_CORE.md`
5. `docs/CORE_CONTRACT.md`
6. `docs/CONVENCIONES.md`
7. `docs/ARCHITECTURE.md`
8. `docs/PLAN.md`
9. `docs/VERSIONADO.md`
10. ADRs recientes en `docs/decision_records/`

Doctrina transversal del ente (repo de gobernanza `ia_nest_meta`), que aplica
aqui y no se duplica en este repo:

- `docs/DOCTRINA_MULTI_IA.md`: roles, modo ciego, regla de la inconsistencia,
  regla del registro, handoff.
- `docs/CONVENCIONES_TRANSVERSALES.md`: docs en ASCII puro, identificadores en
  ingles snake_case, citas `<repo> ADR NNNN`, repo publico.

Versionado: toda propuesta que toque contrato publico declara su impacto
(patch/minor/major) y actualiza `CHANGELOG.md` (`docs/VERSIONADO.md`, ADR 0030).
No cortes tags por tu cuenta; el tag se decide en la reconciliacion del usuario.

Este repo se trabaja con mas de un agente de IA en paralelo, en modo ciego. No
asumas que una inconsistencia entre documentos es un error propio: puede ser
trabajo en curso de otro agente. Senalala, no la corrijas por inferencia.
Ninguna propuesta estructural se aplica sin reconciliacion del usuario.
