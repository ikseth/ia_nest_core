# Instrucciones para Claude Code en este repo

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

Versionado: toda propuesta que toque contrato publico declara su impacto
(patch/minor/major) y actualiza `CHANGELOG.md` (`docs/VERSIONADO.md`, ADR 0030).
No cortes tags por tu cuenta; el tag se decide en la reconciliacion del usuario.

Este repo se trabaja tambien con Codex en modo ciego (ver seccion
"Colaboracion entre varias IA" en `IA_NEST_CORE_CONTEXT.md`). No asumas que
una inconsistencia entre documentos es un error: puede ser trabajo en
curso de la otra IA. Senalala, no la corrijas por inferencia.

No accents/tildes in repo docs: deliberate convention for this project, not
an error to fix.
