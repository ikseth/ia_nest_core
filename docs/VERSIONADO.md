# Versionado del core

Estado: activo
Version del documento: 2.0 - 2026-07-26

La POLITICA de versionado es comun a todo el ente y vive en
`ia_nest_meta/docs/POLITICA_SEMVER.md` (meta ADR 0004): esquema
`MAJOR.MINOR.PATCH`, el tag como fuente de verdad, que numero subir y el proceso
de publicacion. Origen historico: este documento y ADR 0030.

Este documento fija lo que solo el core puede fijar: QUE cuenta como su contrato
publico, y como registra sus correcciones pequenas.

## Que es "contrato publico" (lo que gobierna la version)

El SemVer de este core se mide contra su contrato publico, no contra el codigo
interno. Cuenta como contrato:

- TODAS las capacidades publicas de `docs/CORE_CONTRACT.md`, sin enumerarlas
  aqui (hogar unico, meta ADR 0008): la lista de aquel documento es la
  autoritativa, y una capacidad nueva entra en el contrato publico por estar
  alli, no por aparecer en esta linea.
- El provisioning de modelos (ADR 0029), que es contrato publico y no vive en
  `CORE_CONTRACT.md`.
- El esquema de configuracion (`docs/decision_records/0014`, `0016`).
- El esquema de telemetria: orden/nombres de columnas CSV y `schema_version`
  (ADR 0015).
- Los tipos de evento del flujo D2 (ADR 0004).
- La taxonomia de errores `CoreError` (ADR 0020).
- La version de protocolo MCP declarada (ADR 0006) y la superficie CLI/REST/MCP.

Un refactor interno que no cambia nada de lo anterior NO sube MINOR ni MAJOR
(a lo sumo PATCH si corrige un fallo observable).

## Que numero subir, y como se publica

Regla comun del ente: `ia_nest_meta/docs/POLITICA_SEMVER.md`, secciones 3 y 4.
El core esta en la serie pre-1.0 (`0.y.z`), donde un cambio que rompe contrato
sube MINOR y una adicion compatible o correccion sube PATCH.

Concreciones de este repo, que la politica deja a cada capa:

- Manifiesto de version: `pyproject.toml` (`version`).
- Los tags se cortan sobre `main`.
- Ejemplos de lo que en este core ROMPE contrato: reordenar o renombrar columnas
  de telemetria, cambio no aditivo del esquema de config, cambiar tipos de
  evento D2 o la taxonomia `CoreError` de forma incompatible, quitar o renombrar
  una capacidad de `CORE_CONTRACT.md`.
- Ejemplos de adicion compatible: capacidad opcional nueva, campo aditivo nuevo,
  bandera CLI nueva.

## Registro de correcciones y mejoras pequenas

`docs/fixes/` conserva el contexto operativo de cambios que necesitan mas
detalle que una linea de `CHANGELOG.md`, pero no introducen una decision
estructural que justifique un ADR.

Se crea una ficha cuando el cambio cumple al menos una de estas condiciones:

- cambia comportamiento observable o toca contrato publico de forma compatible;
- incorpora una capacidad pequena;
- corrige un bug cuya causa y criterios de aceptacion conviene conservar;
- afecta a varios archivos o necesita pruebas especificas;
- debe poder ser retomado por otro agente sin reconstruir la conversacion.

No se exige ficha para erratas, formato o cambios mecanicos sin comportamiento
observable. Si el cambio altera arquitectura, alcance, fronteras o una decision
normativa, corresponde un ADR, no una ficha de fix.

Las fichas se agrupan por linea `MAJOR.MINOR` (`docs/fixes/v0.1/`,
`docs/fixes/v0.2/`, `docs/fixes/v1.0/`) y se numeran correlativamente dentro de
cada linea. Deben indicar como minimo: estado, tipo, impacto de version, version
objetivo, problema, cambio, criterios de aceptacion, archivos previstos y
resultado. Los estados son `propuesta`, `implementada` o `descartada`.

La ficha complementa, no sustituye, al `CHANGELOG.md`: si el cambio toca
contrato publico, la entrada de `[No publicado]` enlaza su ficha. Crear o editar
el mecanismo documental no cambia por si mismo la version del producto.

## Colaboracion multi-IA

Regla del registro, comun al ente: `ia_nest_meta/docs/DOCTRINA_MULTI_IA.md`. En
resumen: un agente propone el impacto y NO corta tags por su cuenta; si dos
agentes cambian contrato en paralelo, el usuario reconcilia y decide el numero.
