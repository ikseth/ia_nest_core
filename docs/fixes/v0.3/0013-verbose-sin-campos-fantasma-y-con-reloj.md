# 0013: --verbose sin campos fantasma y con reloj

Estado: propuesta
Tipo: correccion y mejora pequena (render de CLI, extiende la ficha v0.3/0009)
Impacto de version: patch
Version objetivo: v0.3.x

## Problema

Dos cosas del modo `--verbose`, las dos de render y ninguna de comportamiento.

### A. Campos que no existen, renderizados como `None`

En modo `coverage`, la salida de `--verbose` muestra:

    subtarea 0 (iter None) -> humanidades / mistral_nemo
    Iteracion 1: None

Los dos `None` son campos que en ese modo NO EXISTEN, no valores perdidos:

- `cli.py`, render de `subtask_done`, imprime `(iter {payload.get('iteration')})`.
  El registro de subtarea de `pipeline` lleva `iteration` (ficha v0.3/0008); el
  de `coverage` no lo lleva, porque en coverage no hay iteracion de refinamiento
  sobre la misma subtarea: hay ciclos de cobertura.
- `cli.py`, render de `iteration_end`, imprime `Iteracion {n}: {decision}`. El
  `iteration_end` de `coverage` no lleva `decision` porque en coverage NO HAY
  evaluador que decida: el ledger subsume el juicio done/rerun/replan
  (ADR 0038).

Es cosmetico -no afecta al resultado- pero sale en la primera pantalla que ve
quien usa la capacidad, y un `None` en pantalla parece un fallo aunque no lo sea.

### B. El progreso no dice cuando pasa cada cosa

El 2026-08-11 se perdio tiempo comparando una ejecucion de 10 segundos con otra
de casi dos minutos, y la explicacion -que el coste lo domina el volumen de
salida, no el modo ni la version- hubo que reconstruirla a posteriori leyendo
telemetria. Con el tiempo en cada linea de progreso habria estado a la vista:
que subtarea se llevo los dos minutos se ve mirando, no analizando.

La telemetria ya guarda marca ABSOLUTA (`ts` en JSONL y CSV) para correlacionar
entre sistemas. Lo que falta es el relativo, para el humano que mira la consola.

## Cambio

### A. No renderizar lo que no existe

- `subtask_done`: el segmento `(iter N)` se emite solo si el registro trae
  `iteration`. En coverage desaparece, en pipeline no cambia.
- `iteration_end`: la decision se emite solo si el evento trae `decision`. En
  coverage queda `Iteracion N`, en pipeline no cambia.

No se anaden campos al runtime para rellenar el hueco: el hueco es correcto, lo
que estaba mal era pintarlo.

### B. Reloj en el progreso de `--verbose`

Cada linea de progreso de `--verbose` se prefija con el tiempo TRANSCURRIDO
desde el primer evento de la ejecucion, con un decimal:

    [  0.0s] Tarea recibida
    [  1.8s] Plan: 4 unidades
    [ 41.2s]   subtarea 0 -> humanidades / mistral_nemo

Decisiones, y sus motivos:

- **Transcurrido acumulado, no delta por paso.** Con `max_parallel > 1` las
  subtareas se SOLAPAN, asi que "lo que tardo este paso" es una cifra que
  miente. El acumulado esta bien definido siempre, y ademas cuadra con el `real`
  de `time`. Con paralelismo 1, la resta entre lineas adyacentes sigue estando a
  un vistazo.
- **Relativo y no absoluto**, porque el absoluto ya esta en la telemetria y ahi
  es donde sirve: para cruzar con otros sistemas. En consola lo que se quiere
  saber es cuanto llevamos.
- **Lo mide la CLI**, con reloj monotono desde el primer evento. NO se toca el
  runtime, ni el catalogo de eventos D2, ni la telemetria, ni el contrato. Es
  exactamente el caracter de la ficha v0.3/0009, que introdujo `--verbose` como
  render puro.
- **Solo con `--verbose`.** El modo conciso por defecto no cambia ni una linea,
  `--quiet` sigue silenciando el progreso, y `--json` y stdout no se tocan.
- Aplica a las mismas acciones que ya tienen `--verbose` (ficha v0.3/0009), no
  solo a `task run`.

## Criterios de aceptacion

- En `coverage` con `--verbose` no aparece ningun `None`: ni `(iter None)` ni
  `Iteracion N: None`.
- En `pipeline` con `--verbose` la salida conserva `(iter N)` y la decision,
  identicas a hoy (no regresion).
- Con `--verbose`, cada linea de progreso lleva el prefijo de tiempo
  transcurrido; el valor no decrece nunca a lo largo de una ejecucion.
- Sin `--verbose`, la salida es EXACTAMENTE la de hoy, sin prefijo.
- `--quiet` sigue silenciando el progreso; el mensaje de corte de I3 y el de
  degradacion de I4 se conservan.
- stdout, `--json` y la telemetria sin cambios.
- **Digest de conformance INTACTO** (`4fb0278...`): la CLI no participa en la
  bateria de conformance.
- pytest en verde con y sin extras; sin dependencias nuevas.

## Archivos previstos

- `src/ianest_core/cli.py`
- `tests/test_task_interfaces.py` (y las de reasoning si aplica)
- `docs/manual/cli.md`
- `CHANGELOG.md`

## No cubre

- Anadir `iteration` o `decision` a los registros de coverage para que el render
  tenga algo que pintar: seria inventar semantica que ese modo no tiene, y
  ademas tocaria runtime y telemetria por un motivo cosmetico.
- Marca de tiempo en el modo conciso o en `--json`: el conciso existe para no
  estorbar y `--json` ya puede correlacionarse con la telemetria, que lleva `ts`
  absoluto.
- Medir el coste POR PASO. Con fan-out paralelo esa cifra no esta bien definida;
  si algun dia se quiere, sale de la telemetria por `request_id`, no de la
  consola.

## Resultado

(pendiente de implementacion)
