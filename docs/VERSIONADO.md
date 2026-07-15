# Versionado

Estado: activo
Version del documento: 1.0 - 2026-07-15

Regla unica para el usuario, Codex y Claude Code. Toda propuesta que se mergee
declara su impacto de version y actualiza el CHANGELOG. El objetivo es que
cualquiera pueda saber, por el numero de version, si un cambio rompe contrato.

## Esquema

Versionado semantico `MAJOR.MINOR.PATCH`. Los tags de git son `vMAJOR.MINOR.PATCH`
(p.ej. `v0.1.0`). `pyproject.toml` (`version`) SIEMPRE refleja el ultimo tag; el
tag es la fuente de verdad.

## Que es "contrato publico" (lo que gobierna la version)

El SemVer de este core se mide contra su contrato publico, no contra el codigo
interno. Cuenta como contrato:

- Las capacidades de `docs/CORE_CONTRACT.md` (`prompt.run`, `reasoning.run`,
  `domain.route`, `eval.run`, `runtime.health`, provisioning).
- El esquema de configuracion (`docs/decision_records/0014`, `0016`).
- El esquema de telemetria: orden/nombres de columnas CSV y `schema_version`
  (ADR 0015).
- Los tipos de evento del flujo D2 (ADR 0004).
- La taxonomia de errores `CoreError` (ADR 0020).
- La version de protocolo MCP declarada (ADR 0006) y la superficie CLI/REST/MCP.

Un refactor interno que no cambia nada de lo anterior NO sube MINOR ni MAJOR
(a lo sumo PATCH si corrige un fallo observable).

## Que numero subir

**Pre-1.0 (serie `0.y.z`, situacion actual).** El core aun puede cambiar
contrato mientras se estabiliza:

- Cambio que ROMPE contrato (quitar/renombrar una capacidad, cambio no aditivo
  del esquema de config, reordenar/renombrar columnas de telemetria, cambiar
  tipos de evento o taxonomia de error de forma incompatible): sube **MINOR**
  (`0.1.0 -> 0.2.0`).
- Adicion compatible (nueva capacidad opcional, nuevo campo aditivo, nueva
  bandera CLI) o correccion: sube **PATCH** (`0.1.0 -> 0.1.1`).

**Post-1.0 (cuando se declaren estables los contratos).** SemVer estandar:
MAJOR = cambio que rompe contrato; MINOR = capacidad compatible nueva;
PATCH = correccion compatible. El salto a `1.0.0` es una decision explicita del
usuario (con su ADR), no automatica.

## Proceso (los tres lo siguen igual)

1. Toda propuesta que toque contrato publico declara su impacto (`patch` /
   `minor` / `major`) en el commit o PR y anade una linea a la seccion
   `## [No publicado]` de `CHANGELOG.md`.
2. Cambios que no tocan contrato (docs, tests, refactor interno) no exigen
   entrada de CHANGELOG salvo que el autor lo vea util.
3. Publicar una version (accion del usuario, o de un agente a peticion suya):
   - mover las entradas de `[No publicado]` a una seccion `[vX.Y.Z] - FECHA`;
   - fijar `version` en `pyproject.toml` a `X.Y.Z`;
   - commit y tag anotado `vX.Y.Z` sobre `main`;
   - `git push origin main --tags`.

## Colaboracion multi-IA

En modo ciego (ver `IA_NEST_CORE_CONTEXT.md`), si dos agentes proponen cambios
de contrato en paralelo, el usuario reconcilia y decide el numero final. Un
agente NO crea tags por su cuenta: propone el impacto; el tag se corta en la
reconciliacion.
