# Decision 0049: la GPU del backend la declara el backend, no el core

Fecha: 2026-08-15
Estado: reconciliado por el usuario (2026-08-15), enmendado y reconciliado
2026-08-17. **Sin puntos abiertos**: la forma de la sonda queda verificada contra
la version desplegada (ollama 0.12.2), con lo que se cierra la fase 1 de su linea
en el PLAN.

Enmiendas de 2026-08-17, todas reconciliadas por el usuario:

1. `backend.gpu` pasa de objeto a LISTA, con una entrada por endpoint distinto,
   identificada por los `id` de modelo que sirve y no por la URL.
2. `unknown` gana `reason`, para no colapsar sus tres causas.
3. Cuarto estado `partial`: la verificacion demostro que un modelo que no cabe se
   reparte entre memoria de video y procesador, y que la regla anterior lo
   reportaba como `in_use`.
4. Regla de agregacion cuando un endpoint tiene varios modelos cargados: la
   entrada toma el peor estado.
5. El campo se declara INDICADOR BASE; la observabilidad fina es de la capa de
   monitorizacion (ADR 0037).
Depende de: ADR 0003 (protocolo compatible con OpenAI), ADR 0024 (deteccion de
runtime/GPU), ADR 0029 (provisioning backend-especifico), ADR 0028 (estrategia de
recursos de backend)

## Contexto

`runtime.health` informa hoy de la GPU ejecutando `nvidia-smi` **en la maquina
donde corre el core** (`service.py`, `_gpu_status`). Eso fue correcto mientras
core y backend de modelos vivian en el mismo hierro, que es como se valido en
laboratorio en v0.1.

Deja de serlo en cuanto se separan. En una topologia donde el core corre en una
maquina virtual y el backend de modelos vive en un contenedor del anfitrion -que
es hacia donde va el entorno del ente-, el core informara `gpu.available: false`
y estara diciendo la verdad: **en su maquina no hay GPU**. Pero quien lea el
informe entendera otra cosa, porque la pregunta que se hace no es "tiene GPU el
proceso" sino "esta corriendo esto sobre GPU".

Hay ademas un modo de fallo que hoy no se ve y que importa mas que el anterior.
Cuando un modelo no cabe en la memoria de video disponible, el backend no falla:
**cae a CPU en silencio**. Responde bien, con las mismas trazas, y va un orden de
magnitud mas lento. Hoy eso solo se diagnostica midiendo latencias y
sospechando. Es el fallo mas caro de los tres, y el unico invisible.

## Decision

**La GPU del backend la declara el backend.** El core deja de deducir de su
hardware local algo que ya no le pertenece, y pasa a preguntarselo a quien la
usa.

`runtime.health` mantiene DOS campos, con dos significados que no se mezclan:

- `gpu`: el runtime LOCAL, exactamente como hoy. No cambia. En una maquina sin
  GPU dira `available: false`, que es cierto.
- `backend.gpu`: LISTA de lo que cada backend configurado declara sobre su propio
  uso de GPU, con una entrada por endpoint distinto:

      backend.gpu: [
        {
          models: [<id de modelo>, ...],
          reported_by: "ollama" | null,
          status: "in_use" | "cpu_only" | "unknown",
          models_loaded: N,
          reason: <causa, solo cuando status es unknown> | null
        },
        ...
      ]

Los cuatro estados de `status` son necesarios y ninguno es relleno. Por modelo
cargado, comparando lo que ocupa con lo que de eso esta en memoria de video:

- `in_use`: esta entero en memoria de video.
- `partial`: esta a medias. Parte de sus capas se ejecutan en el procesador.
- `cpu_only`: no ocupa memoria de video en absoluto.
- `unknown`: no se pudo determinar. `reason` dice cual de las tres causas es:
  `no_models_loaded`, `backend_unreachable` o `provider_unsupported`. Las tres
  piden acciones distintas del operador, asi que colapsarlas en un solo valor
  sin motivo seria perdida silenciosa.

`partial` y `cpu_only` son los dos valores que justifican la decision entera, y
`partial` es el mas probable de los dos. Un modelo que no cabe **no cae del todo
al procesador**: el backend reparte capas. Verificado (ver mas abajo): un 7B
cuantizado con el 42% en memoria de video responde bien y va varias veces mas
lento, sin un solo aviso.

### Regla de agregacion: la entrada toma el PEOR de sus modelos

Un endpoint puede tener varios modelos cargados a la vez -con una sola tarjeta y
varios dominios, es lo habitual-, asi que la entrada tiene que resumirlos. El
orden de gravedad es:

    cpu_only  <  partial  <  in_use

y la entrada publica el peor. Es el mismo motivo por el que el campo es una lista
y no un objeto: en un informe de salud, un modelo sano no puede tapar a uno
enfermo. `models_loaded` acompana para saber cuantos se estan resumiendo.

Coste aceptado de la regla: la entrada dice que algo va mal en ese backend, no
cual. Levantar la bandera es el trabajo de un informe de salud; averiguar cual es
diagnostico, y para eso basta un comando aparte.

### Por que una LISTA, y por que identificada por modelo

Son dos decisiones separadas y cada una tiene su motivo.

**Lista, no objeto.** El esquema de configuracion admite N modelos y cada uno
declara su propio `endpoint`. Un campo singular tendria que elegir uno en
silencio -y entonces un backend en CPU quedaria tapado por otro en GPU, que es
exactamente el fallo que este ADR existe para destapar- o callarse en cuanto
hubiera mas de uno. Ademas la direccion del entorno del ente es hacia MAS
separacion, no menos: apostar por un solo backend obliga a romper la forma del
campo justo cuando ya haya consumidores. Una lista de un elemento hoy es la misma
lista de tres manana.

**Identificada por los `id` de modelo, no por la URL del endpoint.** El core
agrupa internamente por endpoint resuelto -eso es su fontaneria-, pero lo que
publica son identificadores que ya son publicos: `runtime.health` expone hoy
`id`, `provider`, `available`, `capabilities` y `profile` de cada modelo, y **no
expone endpoints**. Publicar la URL convertiria un informe de salud en un mapa de
la topologia interna, en una interfaz que no tiene autenticacion. Y la pregunta
real del operador no es "que URL esta en CPU", sino **"cuales de mis modelos
estan en CPU"**, que es justo lo que la entrada responde.

El orden de la lista es determinista (por los `id` de modelo de cada entrada),
para que la bateria de conformidad pueda compararla.

Lo que NO se anade: ningun resumen agregado del tipo "algo esta en CPU". Seria el
campo unico que este mismo ADR descarta mas abajo, con el mismo defecto de tener
que mentir en la mitad de las topologias.

**`runtime.health` nunca falla por esta sonda.** Es informe, no diagnostico: si
el backend no contesta, el campo vale `unknown` y el resto del informe sale
igual.

### Por que esto no reabre el agnosticismo del core

El core habla protocolo compatible con OpenAI a proposito (ADR 0003), y ese
protocolo no dice nada de GPUs. La sonda es, por tanto, especifica del backend.

No es la primera y hay costura para ello: el provisioning (ADR 0029) tambien es
especifico de Ollama y se acepto por tres razones que aqui se cumplen igual:
vive FUERA del camino de inferencia, es OPCIONAL, y degrada solo -
`provisioner_for(model)` devuelve `None` cuando el proveedor no se reconoce-. La
sonda entra por esa misma puerta y con el mismo patron.

La linea que no se cruza: el core no pide al backend un inventario de hardware,
ni interpreta modelos de GPU, ni compara memorias. Pregunta una cosa y la
transcribe.

### Lo que NO se hace, y por que

- **No se carga un modelo para averiguarlo.** Sin nada cargado la respuesta es
  `unknown`, y se queda en `unknown`. Un chequeo de salud que provoca una carga
  de GPU deja de ser barato y pasa a tener efectos.
- **No se mezcla con el campo `gpu` local.** Un solo campo "hay GPU" tendria que
  mentir en la mitad de las topologias. Dos campos dicen la verdad en todas.
- **No se declara el modelo de GPU ni su memoria.** Eso es inventario de
  hardware ajeno, y no se necesita para la pregunta que se responde.

## Es un INDICADOR BASE, no observabilidad

Este campo responde una pregunta binaria de operacion -"esto corre sobre GPU o
no"- y se queda ahi a proposito. La observabilidad de verdad -series temporales,
umbrales, historico, latencias correlacionadas con el estado de la GPU- es de la
capa de monitorizacion del ente (ADR 0037), no de un campo de `runtime.health`.

La frontera importa en las dos direcciones. Sin ella, este campo crece hasta ser
un sistema de metricas mal hecho dentro del core; y con ella, cuando exista la
capa de monitorizacion, el core no tiene que retirar nada: seguira publicando el
indicador base y la capa hara lo fino encima.

## Verificacion de la forma (hecha 2026-08-17)

Verificada contra **ollama 0.12.2**, la version que fija
`deploy/ollama.compose.yaml`, en el host de laboratorio y con el compose del repo
sin modificar. Forma CONFIRMADA: `GET /api/ps`, lista `models[]`, y por modelo
cargado los campos `size` (lo que ocupa) y `size_vram` (cuanto de eso esta en
memoria de video). Trae ademas `expires_at`, el instante en que el backend lo
descargara, que explica por que una comprobacion tardia puede ver
`no_models_loaded` sin que nada este roto.

Los cuatro estados se observaron de verdad, ninguno por deduccion: nada cargado,
entero en memoria de video, nada en memoria de video (forzado con `num_gpu: 0`) y
**a medias** (forzado con `num_gpu: 10`, resultado 42% en memoria de video).

Ese cuarto caso es el que corrige la regla: la comprobacion `size_vram == 0` que
prototipo `deploy/setup.sh` solo distingue "nada" de "algo", asi que habria
reportado `in_use` para un modelo con la mayoria de sus capas en el procesador.
La forma estaba bien prototipada; la regla no. Las cifras concretas de la
verificacion viven en el registro de laboratorio, que no se versiona.

Si la forma cambiase en una version futura del backend, la decision de fondo no
cambia: preguntar a quien usa la GPU en vez de mirar el hardware local.

## Alternativas descartadas

- **Dejarlo como esta y explicarlo en el manual.** Barato, pero no resuelve el
  fallo caro: la caida silenciosa a CPU seguiria siendo invisible.
- **Que el core ejecute `nvidia-smi` en el host del backend por SSH o similar.**
  Ataria el core a la infraestructura, exigiria credenciales y romperia que el
  backend sea un endpoint y nada mas.
- **Preguntar al backend por su hardware.** Mas de lo que hace falta, y mete al
  core en el negocio de interpretar GPUs ajenas.
- **Deducirlo de la latencia.** Es una heuristica, y las heuristicas en un campo
  de salud se leen como hechos.

## Consecuencia

- `CORE_CONTRACT.md`: `runtime.health` declara `backend.gpu` como lista, con sus
  tres estados y el `reason` de `unknown`, y se dice explicitamente que `gpu` es
  del runtime local. `runtime.detect` publica el mismo campo, porque comparte
  implementacion con `runtime.health`.
- Bateria: casos de conformidad con sonda guionizada para los tres estados, para
  las tres causas de `unknown`, y para una configuracion con dos endpoints
  distintos (dos entradas, orden determinista).
- Impacto de version: adicion compatible (PATCH). Si se entrega antes de cortar
  la linea v0.4, viaja con ella; si no, en la siguiente.
- La validacion de laboratorio de v0.1 dio por criterio "deteccion GPU" contra
  el host del core. Ese criterio se reinterpreta, no se incumple: en topologia
  separada, lo que hay que verificar es `backend.gpu: in_use`.
