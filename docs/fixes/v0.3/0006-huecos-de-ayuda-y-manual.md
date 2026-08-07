# 0006: huecos de ayuda de la CLI y del manual

Estado: implementada
Tipo: correccion (documentacion y superficie de ayuda)
Impacto de version: patch
Version objetivo: v0.3.0

## Problema

La ayuda de `argparse` esta bien cubierta por `tests/test_cli_help.py` (8
grupos, 13 acciones), pero hay seis huecos fuera de esa cobertura. Uno septimo
-el contrato no documentaba `mode=coverage`- quedo cerrado al fusionar la rama
`docs/v0.3-reconciliation`.

1. **Un grupo sin accion imprime la ayuda RAIZ, no la suya.** `ianest task` cae
   por todos los `if` de `main()` y ejecuta `parser.print_help()` sobre el
   parser de primer nivel. Devuelve 2, que es correcto; muestra la pantalla
   equivocada. Afecta a los ocho grupos.
2. **`docs/manual/cli.md` no menciona `task`.** Su lista de comandos enumera
   nueve y omite `task run`, `model pull` y `reasoning stream`. Es la capacidad
   central de las lineas v0.2 y v0.3.
3. **El manual no documenta `--quiet` ni la separacion stdout/stderr**
   (ADR 0039), que ya estan implementadas.
4. **`runtime health` y `runtime detect` devuelven exactamente lo mismo**:
   `service.health()` es `return detect_runtime(...)`. Sus ayudas describen
   cosas distintas, lo que sugiere dos comportamientos que no existen.
5. **La CLI no tiene `prompt stream`** aunque REST expone `POST /prompt/stream`
   y la CLI si tiene `reasoning stream`. Asimetria contra la regla "la CLI debe
   ser la primera interfaz verificable" (`CORE_CONTRACT.md`).
6. **Texto redundante en `--json`**: sale "emite cada checkpoint como JSONL en
   formato JSON", por componer una plantilla fija con un contenido que ya
   nombra el formato.

## Cambio

1. `main()` imprime la ayuda del GRUPO invocado cuando falta la accion, no la
   raiz. Se conserva el codigo de salida 2.
2. `docs/manual/cli.md` incorpora `task run` (con `--mode`), `model pull` y
   `reasoning stream` a la lista de comandos y a los ejemplos.
3. El manual documenta el modelo de salida de ADR 0039 (stdout la respuesta,
   stderr el progreso) y la bandera `--quiet`.
4. Se alinean las ayudas de `runtime health` y `runtime detect` para que
   declaren lo que de verdad hacen: hoy `health` es un alias de `detect` y
   ambas informan de core, backend, modelos, GPU y version de protocolo MCP
   (decision del usuario, 2026-08-06). No se toca comportamiento: diferenciar
   las dos capacidades habria tocado `runtime.health`, que es contrato publico,
   y eso pide un ADR propio, no una ficha.
5. Se anade `prompt stream` a la CLI, con paridad al `POST /prompt/stream` ya
   existente y al patron de `reasoning stream` (stdout los fragmentos, stderr
   el progreso, `--json` los eventos, `--quiet`).
6. Se corrige la composicion del texto de `--json` para que no nombre el
   formato dos veces.

## Criterios de aceptacion

- `ianest GRUPO` sin accion imprime la ayuda de ese grupo, para los ocho
  grupos; codigo de salida 2. Cubierto en `tests/test_cli_help.py`.
- `docs/manual/cli.md` menciona todas las acciones que la CLI expone. Test que
  compara la lista de acciones del parser con las citadas en el manual, para
  que el hueco no se reabra.
- `prompt stream` figura en `ACTIONS` y en `QUIET_ACTIONS` de
  `tests/test_cli_help.py` y tiene paridad de comportamiento con
  `reasoning stream`.
- Ninguna ayuda repite el formato dos veces.
- pytest en verde con y sin extras; conformance sin cambio de digest (la ayuda
  no toca el runtime).

## Archivos previstos

- `src/ianest_core/cli.py`
- `docs/manual/cli.md`
- `tests/test_cli_help.py`

## No cubre

- El render por formatos (`--format text|md`) y el modo `--debug`: son
  decisiones propias, no huecos de ayuda.
- Diferenciar de verdad `runtime.health` de `runtime.detect` (dos capacidades
  con comportamiento distinto). Descartado aqui por tocar contrato publico;
  si algun dia se quiere, es un ADR.

## Resultado

Implementada en cli.py, el manual y sus pruebas de ayuda.
