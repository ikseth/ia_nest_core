# Decision 0049: la GPU del backend la declara el backend, no el core

Fecha: 2026-08-15
Estado: propuesta; pendiente de reconciliacion del usuario
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
- `backend.gpu`: lo que el backend declara sobre su propio uso de GPU:

      backend.gpu: {
        reported_by: "ollama" | null,
        status: "in_use" | "cpu_only" | "unknown",
        models_loaded: N
      }

Los tres estados de `status` son necesarios y ninguno es relleno:

- `in_use`: hay modelos cargados y ocupan memoria de video.
- `cpu_only`: hay modelos cargados y NO ocupan memoria de video. Este es el
  valor que justifica la decision entera.
- `unknown`: no hay modelos cargados, el backend no responde, o su proveedor no
  se reconoce. `models_loaded` acompaña para que se entienda por que.

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

## Verificacion pendiente antes de congelar

La forma concreta -`GET /api/ps` y el campo `size_vram` por modelo cargado- se
da por buena de lectura y **se verifica contra la version de Ollama desplegada
antes de fijar los valores en el contrato**. Si esa forma cambiase, la decision
de fondo no: preguntar a quien usa la GPU en vez de mirar el hardware local.

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

- `CORE_CONTRACT.md`: `runtime.health` declara `backend.gpu` con sus tres
  estados, y se dice explicitamente que `gpu` es del runtime local.
- Bateria: casos de conformidad con sonda guionizada para los tres estados, y
  test de degradacion cuando el proveedor no se reconoce o el backend no
  responde.
- Impacto de version: adicion compatible (PATCH). Si se entrega antes de cortar
  la linea v0.4, viaja con ella; si no, en la siguiente.
- La validacion de laboratorio de v0.1 dio por criterio "deteccion GPU" contra
  el host del core. Ese criterio se reinterpreta, no se incumple: en topologia
  separada, lo que hay que verificar es `backend.gpu: in_use`.
