# Decision 0030: versionado semantico y proceso de release

Fecha: 2026-07-15

## Decision

Se adopta versionado semantico `MAJOR.MINOR.PATCH` con tags de git `vX.Y.Z`,
medido contra el CONTRATO PUBLICO del core (capacidades de `CORE_CONTRACT.md`,
esquema de config, esquema de telemetria, eventos D2, taxonomia de error,
version MCP y superficie CLI/REST/MCP), no contra el codigo interno.

- Pre-1.0 (serie `0.y.z`): un cambio que rompe contrato sube MINOR; una adicion
  compatible o correccion sube PATCH.
- Post-1.0 (contratos declarados estables, decision explicita del usuario):
  SemVer estandar.
- `pyproject.toml` refleja el ultimo tag (el tag es la fuente de verdad).
- Toda propuesta que toque contrato declara su impacto y actualiza
  `CHANGELOG.md`. Un agente no corta tags por su cuenta; el tag se decide en la
  reconciliacion del usuario.

La regla operativa completa vive en `docs/VERSIONADO.md`.

## Motivo

El core es "contratos pequenos y versionados" (ADR 0004, `CORE_CONTRACT.md`).
Sin un criterio de version compartido, los tres participantes (usuario, Codex,
Claude Code) no pueden saber por el numero si un cambio rompe algo, ni las
capas externas (`FRONTERAS.md`) pueden depender del core con seguridad.

## Consecuencia

- Primer tag: `v0.1.0` sobre el core ya cerrado y validado (fases 1-10 + lab +
  provisioning). `CHANGELOG.md` inicia con esa entrada.
- Las capas externas pueden fijar una version del core como dependencia.
- Cada release sigue el proceso de `docs/VERSIONADO.md` (mover CHANGELOG, fijar
  pyproject, tag anotado, push con tags).
