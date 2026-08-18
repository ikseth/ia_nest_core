# 0004: `runtime.health` tarda decenas de segundos cuando el backend no responde

Estado: propuesta
Tipo: correccion de comportamiento (no toca contrato publico)
Impacto de version: patch
Version objetivo: v0.4.x

## Problema

`runtime.health` comprueba la disponibilidad de cada modelo configurado
sondeando su endpoint. Esa sonda tiene **timeout de 10 segundos** y se ejecuta
**una vez por MODELO**, en serie, sin agrupar por endpoint y sin cache
(`registry/availability.py`, `_probe_openai_models`; se invoca desde
`ModelRegistry.model_records()`, que llama a `is_available` por cada modelo).

Consecuencia, medida:

    2 modelos sobre un endpoint muerto   ->  20,2 s
    plantilla `lab`, 4 modelos           ->  ~40 s previstos

Y ocurre precisamente cuando mas se consulta: **el informe de salud tarda mas
cuanto peor esta el sistema**. Un `GET /runtime/health` que responde en 40 s no
sirve como sonda de salud para nada que lo consulte con periodicidad, y es la
llamada que un operador hace primero cuando algo va mal.

Los modelos con `provider: fake` o endpoint `fake://` estan exentos, asi que la
bateria de conformidad no lo ve. Se destapo midiendo a mano contra un endpoint
inexistente.

## Lo que NO es

No es una regresion de la sonda de GPU de ADR 0049. Se comprobo por separado:

    la sonda de GPU sola, IP no enrutable   2,0 s   (respeta su timeout)
    model.list, que no usa la sonda        20,2 s
    runtime.health ANTES de ADR 0049       20,5 s

El coste es anterior y vive en la comprobacion de disponibilidad. La sonda de
GPU anade 2 s acotados y agrupa por endpoint, que es justo lo que aqui falta.

## Cambio

Tres piezas, y la primera sola ya resuelve el grueso:

1. **Agrupar por endpoint resuelto.** Varios modelos que comparten backend se
   resuelven con UNA sonda, no con N. Es el mismo patron que ya usa
   `backend.gpu`. En la plantilla `lab` eso divide el coste por cuatro.
2. **Timeout mas corto y explicito**, del orden del de la sonda de GPU. Diez
   segundos era razonable para una llamada puntual y no lo es para un informe
   que se consulta en bucle.
3. **Presupuesto total de la comprobacion**, no solo por sonda. Con muchos
   endpoints distintos el coste vuelve a sumar; un tope global lo acota, y lo que
   no de tiempo se reporta como no disponible, que es la respuesta honesta.

Lo que NO se cambia: el significado de `available`. Un endpoint que no contesta
sigue dando `available: false`. Esto es coste, no semantica.

## Criterios de aceptacion

- Con N modelos sobre un mismo endpoint caido, `runtime.health` hace UNA sonda,
  no N. Verificable contando llamadas con un doble.
- Con el backend caido, `runtime.health` responde por debajo del presupuesto
  declarado, y ese presupuesto esta escrito, no implicito.
- `available` conserva su semantica: mismo valor que hoy en todos los casos de
  conformidad.
- El digest de conformidad no se mueve: los fixtures usan `fake://`, exentos de
  la sonda. Si se moviera, hay que entender por que antes de declararlo.
- Un caso de conformidad nuevo que fije el agrupamiento, para que no se pierda.

## Archivos previstos

- `src/ianest_core/registry/availability.py`
- `src/ianest_core/registry/model_registry.py`
- `eval/battery/`, `eval/README.md` si el caso nuevo lo requiere
- `CHANGELOG.md`

## No cubre

- La forma del informe ni el contrato de `runtime.health`: no cambian.
- El camino de inferencia, que no usa esta comprobacion.
- Cachear disponibilidad entre llamadas: seria otra decision, con su propia
  cuestion de frescura, y no hace falta para resolver esto.

## Resultado

Pendiente.
