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

Doctrina transversal del ente, en el repo de gobernanza `ia_nest_meta`:
`docs/DOCTRINA_MULTI_IA.md`, `docs/CONVENCIONES_TRANSVERSALES.md`,
`docs/REGISTRO_CAPAS.md` (quien depende de quien) y `docs/change_requests/`
(CR abiertos hacia este repo). Aplica aqui y no se duplica en este repo.

Este repo se trabaja tambien con Codex en modo ciego. No asumas que una
inconsistencia entre documentos es un error: puede ser trabajo en curso de la
otra IA. Senalala, no la corrijas por inferencia.

No accents/tildes in repo docs: deliberate convention for this project, not
an error to fix.
