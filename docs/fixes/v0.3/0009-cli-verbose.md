# 0009: modo --verbose en la CLI (progreso rico del flujo)

Estado: implementada
Tipo: mejora (superficie CLI, extiende ADR 0039)
Impacto de version: patch
Version objetivo: la de la linea del router (con la que se entrega)

## Problema

El progreso de la CLI en las capacidades que emiten flujo es CONCISO: en
`task.run` se ve "Tarea recibida", "Plan listo: N unidades", "Subtarea
completada", "Iteracion N completada". El usuario, para seguir COMO fluye la
accion, echa en falta ver a que MODELO/DOMINIO fue cada subtarea y en que
ITERACION va -era la peticion #1 de la revision (telemetria de steps y modo
debug)-. Hoy solo hay dos extremos: conciso (default) o `--json` (todo
estructurado). Falta el punto medio legible.

Los datos YA viajan en los eventos D2 (no hace falta tocar runtime ni
telemetria): `subtask_done` lleva `index`, `iteration`, `domain`, `model`;
`iteration_end` lleva `iteration`, `decision`; el `step` de reasoning lleva
`iteration`, `done`. La CLI simplemente no los renderiza.

## Cambio

Nueva bandera `--verbose` (aditiva, como `--quiet` en ADR 0039), en las mismas
CINCO acciones que ya tienen `--quiet`: `prompt run`, `prompt stream`,
`reasoning run`, `reasoning stream`, `task run`. Enriquece el progreso de stderr
con los datos que ya traen los eventos. Espectro resultante:

    --quiet    -> solo la respuesta (silencio)
    (default)  -> progreso conciso (como hoy, sin cambios)
    --verbose  -> progreso rico (modelo, dominio, iteracion por paso)
    --json     -> eventos estructurados (sin cambios)

Render en modo `--verbose`:

- `task.run`:
  - `plan_ready`: `Plan: N subtareas` (pipeline) / `Plan: N unidades` (coverage).
  - `subtask_done`: `  subtarea {index} (iter {iteration}) -> {domain} / {model}`.
  - `coverage_updated`: `  cobertura {completadas}/{total} (pendientes P, fallidas F)`.
  - `iteration_end`: `Iteracion {iteration}: {decision}`.
  - `combine_ready`: como hoy (respuesta preparada / combinacion sin respuesta).
- `reasoning.run`/`stream`:
  - `step`: `Paso {iteration} (done={done})`.

Reglas:

- El modo default (sin bandera) NO cambia: mismas lineas concisas de hoy.
- `--quiet` silencia el PROGRESO (conciso y verbose por igual). NO silencia el
  mensaje de CORTE de tarea (I3: "Tarea cortada: ..."), que no es progreso sino
  el desenlace y se conserva como hoy, con o sin `--verbose`/`--quiet`.
- `--quiet` tiene precedencia sobre `--verbose` para el progreso (si ambos, no
  se imprimen las lineas de progreso; el corte I3 sigue mostrandose).
- `--verbose` no cambia stdout (la respuesta) ni `--json`.
- Solo render de CLI: NO toca runtime, telemetria, ni el catalogo de eventos D2.

## Criterios de aceptacion

- `task run --verbose` muestra, por subtarea, `{domain}/{model}` y la iteracion;
  `iteration_end` muestra la decision. Test lo cubre.
- `reasoning --verbose` muestra el numero de paso y `done`.
- El modo default (sin `--verbose`) produce EXACTAMENTE las mismas lineas de hoy
  (no regresion en `tests/test_task_interfaces.py` ni en las de reasoning).
- `--quiet` sigue silenciando el PROGRESO (con o sin `--verbose`); un corte de
  tarea sigue mostrando su mensaje I3 en stderr (no regresion).
- `--json` sin cambios; stdout (la respuesta) sin cambios.
- `--verbose` esta en las 5 acciones que tienen `--quiet` (incluye
  `prompt stream`).
- pytest en verde con y sin extras; digest de conformance SIN cambio (la CLI no
  participa en conformance).

## Archivos previstos

- `src/ianest_core/cli.py`
- `tests/test_task_interfaces.py` (y las de reasoning si aplica)
- `docs/manual/cli.md` (documentar `--verbose` en el espectro de salida)

## No cubre

- Mostrar el MOTIVO/confianza del router por subtarea (necesitaria guardar la
  decision del router en el registro de subtarea: es un toque de runtime).
  Decision del usuario (2026-08-10): fuera de esta ficha; solo modelo/dominio/
  iteracion.
- La correlacion en el CSV de telemetria (columnas `task_id` etc., punto B3):
  es persistencia, no la vista en vivo; su propio ADR (rompe esquema congelado).

## Resultado

Implementada como bandera `--verbose` en las 5 acciones con `--quiet`. El
progreso rico sale del payload de los eventos D2 (subtarea con
`index`/`iteration`/`domain`/`model`, decision de iteracion, paso/done de
reasoning); el modo default y el corte I3 no cambian. Solo render de CLI, sin
tocar runtime ni digest (6dcae1a5 estable). Dos ambiguedades de la ficha las
detecto el codificador antes de implementar (verbose en `prompt stream`; el
corte I3 no se silencia con `--quiet`) y se reconciliaron aqui.
