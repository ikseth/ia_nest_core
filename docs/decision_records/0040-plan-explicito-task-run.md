# Decision 0040: enriquecimiento por subtarea en task.run (extended CR-0001): granularidad de la entrada, no costura nueva

Fecha: 2026-07-27

## Decision

Se REFORMULA `extended CR-0001`. Se acepta la NECESIDAD y se descarta la FORMA
sugerida (un checkpoint `subtask_enrich` que admite de vuelta un bloque de
contexto).

### Primero: de quien es cada mitad

La necesidad que trae el CR son dos necesidades, y solo una es del core.

- **N1: saber que dominio le toca a cada subtarea, antes de que corra su
  modelo.** Esa informacion solo la produce el core: es el resultado de su
  planificador y de su precedencia de ruteo (ADR 0019). Ninguna capa de encima
  puede derivarla. Hacerla utilizable es responsabilidad del core.
- **N2: meter el conocimiento de ese dominio en el prompt de esa subtarea.** Es
  enriquecimiento. Vive en la capa, decidido en ADR 0031 (via 2) y confirmado
  al retirar `MemoryPort` (ADR 0035). NO es responsabilidad del core.

La forma sugerida por el CR mezcla las dos: una costura que devuelve contenido
mete al core dentro de N2. Esta decision las separa.

### La forma: el plan como dato de entrada

1. **Nueva capacidad `task.plan`.** Ejecuta solo la etapa PLAN de `task.run`
   (ADR 0036) y devuelve el plan SIN ejecutarlo. Por subtarea: `index`,
   `prompt`, `domain` (ya resuelto con la precedencia de ADR 0019),
   `domain_hint_ignored` cuando proceda, y `depends_on`. Ademas `params` y
   traza. No ejecuta subtareas, ni COMBINE, ni EVALUATE. La descomposicion se
   queda donde es suya: en el core.

2. **`task.run` acepta un `plan` de entrada, opcional.** Si viene, el core no
   llama al planificador: valida el plan y entra directo en FAN-OUT. Entre las
   dos llamadas, la capa antepone a cada `prompt` el contexto de su dominio. El
   core no sabe que hay dentro del prompt, igual que en `prompt.run`.

Reglas del contrato:

- Sin `plan`, `task.run` se comporta EXACTAMENTE como hoy. Opt-in, cero
  regresion, determinismo intacto.
- El plan suministrado se valida con las reglas ya vigentes y sus errores
  tipados: forma (`PlanParseError`), dependencias ciclicas o indices invalidos
  (`PlanDependencyError`), tamano (corte `max_subtasks`).
- **Con plan suministrado NO se re-planifica.** Si EVALUATE decide `replan`, la
  tarea corta con un motivo tipado nuevo: `replan_unavailable`. RERUN sigue
  disponible (re-ejecuta el mismo plan, ya enriquecido). Quien tiene el
  conocimiento re-planifica y vuelve a llamar; el core no fabrica en silencio
  subtareas sin enriquecer.
- `plan_ready` gana el campo `plan_source`: `planner | supplied`. Quien observa
  la tarea -telemetria hoy, conscience manana- tiene que poder ver que subtareas
  llevaban prompt escrito por otra capa.
- Paridad (ADR 0036): `ianest task plan`, `POST /task/plan` y herramienta MCP;
  y `plan` como entrada de `POST /task/run`, de su herramienta MCP y de
  `ianest task run` (por fichero: un plan como argumento de linea de comandos es
  hostil).
- Alcance: `mode=pipeline`. `mode=coverage` queda FUERA: extended no lo pidio y
  extenderlo por inferencia seria diseno no reconciliado.

## Motivo

### Las tres costuras que el core ya tiene

El core no carecia de punto de enlace con las capas de encima. Tiene tres, y
estan repartidas por direccion:

- **Entrada de contenido: el prompt.** Agnostico por construccion: el core no
  parsea lo que lleva dentro ni sabe si viene de RAG, de memoria, de un fichero
  o de un humano. Es la via 2 de ADR 0031.
- **Clave de segmentacion: la identidad** (`user_id`, `service`, `session_id`,
  `domain_tag`, `namespace`) en cada request y cada traza. Es la mitad de
  ADR 0011 que ADR 0035 conservo a proposito, y es el enganche por el que cada
  capa indexa lo suyo.
- **Salida de observacion: checkpoints y telemetria.** Eventos D2 por SSE, CSV y
  JSONL. Es un bus, y es de solo lectura a proposito.

Lo que a `task.run` le falta no es un mecanismo nuevo: es GRANULARIDAD. En
`prompt.run` el prompt lo compone quien llama. En `task.run` los prompts de
subtarea los compone el core por dentro, y ahi se corta la cadena. La entrada
`plan` no abre una costura: extiende hasta el nivel de subtarea la costura de
entrada que ya existe.

### Lo verificado en el codigo, antes de valorar la forma sugerida

**1. Los checkpoints actuales son de una sola direccion.** `_checkpoint`
(`task_runtime.py:999`) apunta el nombre, graba telemetria y devuelve
`Event(name, data)`. Los seis anclajes (lineas 206, 210, 219, 222, 224 y 264)
hacen `yield self._checkpoint(...)` y descartan el valor de la expresion
`yield`. Nada en el core lee un retorno de un checkpoint, y sobre REST son
tramas SSE: un medio sin canal de vuelta por construccion. La descripcion del
CR -"hermano de los observables/vetables de ADR 0034"- no se sostiene.

**2. Lo que pide el CR no es la extension diferida de ADR 0036.** El VETO
diferido es un camino de vuelta, si, pero del tipo bloquear o replantear: una
decision de control sobre contenido ya compuesto. El CR pide CONTRIBUIR
contenido a la entrada. Ademas, ese mismo ADR descarta por escrito "checkpoints
como puertos de callback (leccion ADR 0035)". Y aunque el VETO existiera hoy, se
engancharia a los anclajes ya definidos: no hay ninguno antes de ejecutar una
subtarea. `subtask_done` se emite en la linea 219, desde el bucle principal,
DESPUES de que `_fan_out` haya retornado (linea 216).

**3. El punto de insercion cae dentro del pool de hilos.** `_run_subtask`
(linea 931) se ejecuta en un `ThreadPoolExecutor` (linea 921) dentro de
`_fan_out` (linea 914), que es una funcion normal llamada desde el generador.
Una costura ahi no puede ser un evento del stream -no se puede ceder al
generador padre desde un hilo trabajador-: tiene que ser una llamada sincrona,
reentrante, desde hasta `max_parallel` hilos a la vez, que devuelva valor en
linea. Eso es exactamente un puerto de callback: el patron que ADR 0035 retiro y
que ADR 0036 descarto.

**4. El consumidor real no puede consumir un puerto en proceso.**
`ia_nest_extended` habla con el core por su contrato REST publico:
`src/ianest_extended/clients.py` es un cliente HTTP contra
`POST {base_url}/prompt/run`, y su `pyproject.toml` no depende de `ianest_core`.
No importa el core: lo llama como servicio. Un proveedor registrado en el
proceso del core le es inalcanzable. Para llegar a el desde dentro del bucle, el
core tendria que llamar SALIENTE a un endpoint de extended: invertiria el grafo
de dependencias (`meta REGISTRO_CAPAS.md`, origen ADR 0032), conoceria el
enriquecimiento como servicio al que llamar, y acoplaria su latencia y su
determinismo a una capa de encima. La forma sugerida no es solo incomoda
doctrinalmente: es inoperante para quien la pide.

**5. La premisa tecnica del CR no se sostiene en la implementacion actual.** El
CR sostiene que armar el prompt de cada subtarea "solo puede ocurrir DENTRO del
bucle". No es asi: `_run_subtask` usa `item["prompt"]` tal cual viene del plan
(lineas 940 y 945), y `depends_on` (linea 1040) solo ORDENA la ejecucion: los
resultados de las predecesoras NO se inyectan en el prompt de las dependientes
-`_fan_out` pasa unicamente `plan[index]`-. El contenido de todos los prompts
esta fijado en el momento del PLAN. Dentro del bucle no hay ni una informacion
que no estuviera disponible justo despues de planificar.

Ese quinto punto es el que permite reformular sin perder nada de lo pedido.

### Por que no un bus bidireccional generico

Se considero, y se descarta HOY, no para siempre. Un punto de enlace generico
donde cualquier capa devuelva contexto le pone al core dos facturas:

- **Dependencia invertida.** Las capas de encima son otros procesos y hablan
  REST. Un bus real seria el core llamando afuera o esperando a un broker: su
  determinismo y su latencia pasarian a depender de quien este suscrito.
- **Generalidad especulativa.** Es literalmente la leccion de ADR 0035: la
  costura se construye para el consumidor que hay, no para los que se imaginan.
  Hoy hay un consumidor (extended) y una necesidad (conocimiento por dominio en
  cada subtarea).

Ademas mezclaria dos cosas distintas: el VETO es una decision de control,
acotada, propia del supervisor, que por diseno esta por encima y puede bloquear;
la inyeccion es aportar contenido, y la doctrina ya se la dio a la capa por el
prompt.

Esta decision NO cierra esa puerta. La entrada `plan` es aditiva y ortogonal:
el dia que exista una necesidad real de veto, se construye encima, sobre los
anclajes que ADR 0036 ya dejo fijados, y con el consumidor delante.

### La nota sobre conscience, dicha con precision

conscience es posterior a extended y todavia no esta sembrado. No se invoca aqui
como urgencia sino como puerta: su costura con el ente son los checkpoints de
`task.run` (ADR 0034). Si el pensar multi-dominio real acabase ocurriendo dentro
del bucle de otra capa, el supervisor llegaria a observar la rama vacia. Mantener
hoy esa puerta abierta cuesta una entrada de contrato; reabrirla despues costaria
mover una capa entera. El campo `plan_source` es lo que le permitira, cuando
llegue, distinguir que subtareas llevaban prompt de fuera.

## Lo que esta forma cuesta, dicho sin adornos

- Una vuelta de red mas por tarea.
- La capa se queda el ciclo de re-planificacion: si el core quiere replantear,
  corta y devuelve el mando.
- Es una apuesta a que los prompts de subtarea sigan fijandose en el PLAN. Si
  algun dia las subtareas dependientes recibieran el resultado de sus
  predecesoras en el prompt, el enriquecimiento en tiempo de plan enriqueceria un
  prompt que aun no es el definitivo. Degradaria con elegancia -seguiria
  enriqueciendo lo estatico- y esa seria la evidencia para reabrirlo.
- Dos entradas nuevas de contrato publico, sostenidas bajo SemVer para siempre.
  Este es el coste real: el codigo son unas 35 lineas y su bateria; el contrato
  no se borra.

## Consecuencia

- `CORE_CONTRACT.md`: `task.plan` como capacidad nueva; `task.run` gana la
  entrada `plan` opcional, el corte tipado `replan_unavailable` y el campo
  `plan_source` en `plan_ready`.
- Impacto de version: MINOR (adicion compatible; nada de lo existente cambia de
  comportamiento). Version objetivo: la primera linea MINOR posterior a la v0.3
  en curso. El numero lo corta el usuario en la reconciliacion
  (`meta POLITICA_SEMVER.md`, ADR 0030).
- Validacion que sale gratis, ya escrita: forma de subtarea (`_valid_subtask`),
  ciclos e indices invalidos (`_dependencies` mas el chequeo de `ready` vacio en
  `_fan_out`), tope `max_subtasks`, y el techo `max_context_tokens`, que cuenta
  los prompts enriquecidos como cualquier otro: la capa no puede esquivar el
  presupuesto del motor.
- Bateria ANTES de implementar, como en v0.1 y v0.2: plan suministrado valido;
  plan invalido de forma; plan con ciclo o indice invalido; plan que excede
  `max_subtasks`; decision `replan` con plan suministrado -> corte
  `replan_unavailable`; `plan_source` correcto en las dos vias; y no regresion
  (sin `plan`, salida identica a la actual).
- `extended`: al entregarse, mueve su pin de `core >=0.2 <0.3` a la version que
  lleve esto (`ia_nest_extended/docs/DEPENDENCIAS.md`). Su Fase 5 puede avanzar
  entretanto con RAG upfront para `prompt.run`, que no depende de esto.
- `extended CR-0001` pasa a estado `reformulado` en `ia_nest_meta` y permanece en
  `solicitado/` hasta la entrega.
- ADR 0035 no se reabre: no hay puerto, ni proveedor registrado, ni llamada del
  core hacia arriba. Hay un dato mas en la peticion.
- Alternativas descartadas:
  - El checkpoint `subtask_enrich` con valor de vuelta (puntos 1 a 4 del
    motivo).
  - Un puerto de enriquecimiento en proceso al estilo `MemoryPort`: inalcanzable
    para el consumidor real, y reabre ADR 0035 sin necesidad.
  - Que el core llame a un endpoint de enriquecimiento de extended: invierte el
    grafo de dependencias.
  - Un bus bidireccional generico: dependencia invertida mas generalidad
    especulativa (seccion propia arriba). Descartado hoy, no cerrado.
  - **Que extended se orqueste a si misma, sin tocar el core.** Es viable HOY,
    con `core >=0.2`: descomponer con `prompt.run`, rutear con `domain.route`
    -que ya devuelve dominio, modelo, confianza y alternativas-, enriquecer y
    ejecutar subtarea a subtarea. No se descarta por imposible sino por reparto:
    pondria un segundo orquestador dentro de la capa de memoria, duplicando
    planificador, fan-out, limites, cortes tipados y arbol de telemetria, y
    dejaria `task.run` como rama muerta para todo trabajo con conocimiento.
    Contradice la identidad del core como orquestador (ADR 0034). Es la opcion
    que, bajo la regla del canal ("si se puede resolver en la propia capa, no es
    un CR"), habria hecho improcedente el CR; se registra que la decision de no
    tomarla es de reparto de responsabilidades, no de imposibilidad tecnica.
  - **Solo la entrada `plan`, sin `task.plan`.** Mas barata en contrato, pero
    deja la descomposicion en extended, que es tarea de orquestacion y por tanto
    del core. Se descarta por la misma razon que la anterior, en pequeno.
  - Que el propio modelo consulte el RAG (herramienta): revierte ADR 0031 (RAG
    es enriquecimiento, no herramienta) y exige `tool_contracts`, diferido desde
    ADR 0022. Es una decision distinta y de otro tamano; no se toma aqui.
  - Dejar el RAG de `task.run` upfront y grueso: es justo lo que no cabe en el
    presupuesto de tokens observado, con evidencia de laboratorio en el CR.
