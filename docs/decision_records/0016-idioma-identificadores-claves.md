# Decision 0016: idioma de identificadores y claves

Fecha: 2026-07-11

## Decision

Los identificadores de codigo y las claves de configuracion se escriben en
ingles snake_case (`description`, `preferred_model`, `fallback_models`,
`routing_rules`, `status`...). La prosa de la documentacion sigue en espanol
sin tildes.

## Motivo

Evitar mezclar espanol con Python y las librerias (en ingles), reducir
friccion y ambiguedad, y cumplir la regla de nombres normalizados de
`CONVENCIONES.md` sin choques de idioma. Reconcilia el finding F3 de la
auditoria de Codex.

## Consecuencia

- El esquema de configuracion (ADR 0014) usa claves en ingles.
- Se anade la regla a `CONVENCIONES.md`.
- La documentacion narrativa no cambia: sigue en espanol sin tildes.
