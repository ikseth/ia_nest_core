# Decision 0041: criterios de gestion de tareas del orquestador (adecuacion semantica, presupuesto, cortes no silenciosos y degradacion declarada)

Fecha: 2026-08-06
Estado: reconciliado por el usuario (2026-08-06); extendido con el invariante I4
el 2026-08-11, tambien reconciliado

## Decision

`task.run` incorpora tres invariantes que el orquestador comprueba sobre su
PROPIO estado (plan, ledger, presupuesto), sin que ningun modelo juzgue a otro
modelo. Aplican a los dos modos (`pipeline` y `coverage`).

(Un cuarto invariante, I4, se anadio el 2026-08-11 como extension al final de
este documento. El cuerpo original se conserva tal como se reconcilio el
2026-08-06; solo el titulo y esta nota se han actualizado, para que el recuento
no quede desmentido por el propio texto.)

### I1: adecuacion semantica (todo requisito del prompt tiene unidad)

La etapa de planificacion (PLAN en pipeline, DERIVE en coverage) pasa a emitir
DOS listas en la MISMA llamada:

- `requirements`: los requisitos que el planificador extrae del prompt, con id
  y enunciado;
- las unidades/subtareas de siempre, cada una declarando `covers`: la lista de
  ids de requisito que atiende.

El core comprueba EN CODIGO, sin llamada adicional y de forma determinista, que
todo requisito tenga al menos una unidad que lo cubra.

Si quedan requisitos huerfanos:

1. Se re-deriva UNA vez, con los requisitos sin cubrir explicitos en la
   instruccion.
2. Si la segunda derivacion tampoco los cubre, **la tarea continua** y lo
   declara: se ejecuta el plan que haya y el resultado sale marcado.

El contador de re-derivaciones queda fijado en 1 por contrato. No se anade
parametro de configuracion: no hay caso que justifique hacerlo regulable
(anti-entropia). Si aparece, se promueve entonces.

### I2: un limite negocia antes de matar

`max_subtasks` deja de ser muerte subita. Un plan que excede el techo se
devuelve al planificador UNA vez, con el presupuesto explicito en la
instruccion ("dispones de N unidades; agrupa lo que haga falta").

I1 e I2 comparten el mismo contador: **una sola re-derivacion por tarea**, sea
por requisitos huerfanos, por presupuesto o por ambos a la vez. Si la segunda
derivacion sigue sin caber, se corta con `max_subtasks`, ahora bajo I3.

### I3: ningun corte por limite se presenta como exito

Un corte por limite no puede devolver la cadena vacia presentada como
resultado. Regla uniforme para todos los cortes tipados:

- el resultado incluye lo producido hasta el corte (puede ser nada, pero
  entonces se dice);
- la CLI termina con codigo de salida distinto de cero y explica el corte por
  stderr;
- REST y MCP lo transportan como lo que es: una terminacion por limite, no un
  `task_done`.

`task_done` queda reservado a la terminacion por merito propio.

### Campos nuevos (todos aditivos)

En `plan_ready`:

- `requirements`: lista de requisitos derivados (id, enunciado);
- `plan_attempts`: 1 o 2;
- `requirements_covered`: booleano;
- `uncovered_requirements`: lista de ids (vacia si `requirements_covered`).

En el resultado de `task.run`:

- `requirements_covered` y `uncovered_requirements`.

### Relacion con `coverage_complete`

Son sellos distintos y ninguno implica al otro:

- `coverage_complete` (ADR 0038): las unidades del plan quedaron respondidas.
- `requirements_covered` (esta decision): el plan cubria lo que el prompt pedia.

Los dos a la vez son la condicion de "la respuesta encaja con la pregunta". Uno
solo no lo es, y la evidencia de laboratorio de mas abajo es exactamente ese
caso: `coverage_complete=true` sobre un plan que habia perdido la mitad de la
peticion.

Ninguno de los dos acredita EXACTITUD FACTUAL. Eso sigue fuera del core
(ADR 0025, ficha v0.3/0003).

## Motivo

### La evidencia

Telemetria del host de laboratorio, prompt "Enumera los ocho planetas del
sistema solar en orden desde el Sol y explica brevemente cada uno", ocho
ejecuciones el 2026-08-05 (detalle en `local/lab/`, no versionado):

- Seis derivaron 16 unidades (`planetaN` + `descripcionN`, que es la
  descomposicion CORRECTA segun DERIVE de ADR 0038) y murieron en
  `max_subtasks` contra el techo de 12, devolviendo **cadena vacia** con exito
  aparente.
- Una derivo 8 unidades que perdieron por completo el requisito "explica
  brevemente cada uno", se ejecuto entera, y devolvio
  `coverage_complete=true`, `failed_units=[]`, `stop_reason=task_done` sobre
  una respuesta que no respondia a la mitad de lo pedido.
- Es decir: **el plan bueno es el que moria y el plan mutilado es el que
  pasaba**. Con el mismo prompt, el resultado dependia del muestreo del
  planificador.

Los tres invariantes atacan esa evidencia por sus tres costuras: I1 el plan que
pierde requisitos, I2 el techo que mata al plan bueno, I3 el corte que se
disfraza de exito.

### Por que verificar el PLAN y no la RESPUESTA

La forma intuitiva de esta necesidad es "que el orquestador compare el prompt
inicial con el resultado". Se descarta, por dos razones independientes.

**La primera es doctrinal y ya estaba tomada.** ADR 0025 registro y descarto
para el core exactamente eso ("verificar la respuesta con un modelo de
control"), asignandolo a `ia_nest_core_conscience`; `CAPAS_FUTURAS.md` lo
conserva en el reparto de deudas. Esta decision NO reabre ADR 0025: no verifica
la respuesta, verifica que la descomposicion cubra la peticion. Es una
comprobacion sobre el plan, que es estado interno del orquestador y de nadie
mas.

**La segunda es empirica, y pesa mas.** En la misma ejecucion de laboratorio,
el validador de coverage -el mismo modelo que genero los fragmentos- certifico
como cubierta una respuesta que dice dos veces "Marte" y omite Jupiter. Pedirle
a ese modelo que ademas juzgue si la respuesta encaja con la pregunta es
pedirle que detecte el error que acaba de cometer: anade coste y varianza, no
verdad. Por eso la verificacion factual pertenece a una capa con modelo,
criterio y presupuesto propios.

I1 evita esa trampa por construccion: no pregunta a un modelo si el trabajo
esta bien. Pide al planificador que declare lo que ha entendido, y despues
comprueba en codigo, de forma determinista, que su propio plan sea consistente
con lo que declaro.

### Por que el momento es el plan, no el final

Verificar al final informa del fallo cuando ya se han gastado todas las
llamadas y la unica reaccion posible es rehacerlo todo. Verificar el plan
cuesta cero llamadas adicionales -son dos listas en la respuesta que ya se
pedia- y actua antes del fan-out, que es donde esta el gasto.

### Por que ahora, y no antes

ADR 0038 dejo esto escrito: "EVALUATE/replan no participan en modo coverage v1
[...] Re-derivar unidades a mitad de tarea queda **diferido sin caso
demostrado** (anti-entropia)". La condicion para reabrirlo no era una idea
mejor: era un caso. El caso existe, esta medido y esta arriba.

### Sobre determinismo

Lo que fallo no es la falta de idempotencia: con un planificador estocastico
esa solo se consigue cacheando planes, y una cache de planes es memoria
(`ia_nest_extended`, ADR 0035). Lo que faltaba eran INVARIANTES que se cumplan
sea cual sea el muestreo. Los tres se comprueban contra el estado interno del
core, que es el criterio de `IA_NEST_CORE_CONTEXT.md` para decidir si algo es
core o herramienta externa.

## Consecuencia

- `CORE_CONTRACT.md`: `task.run` gana los campos aditivos de arriba, la regla
  de re-derivacion unica (I1/I2) y la regla de cortes no silenciosos (I3). El
  catalogo de cortes tipados no crece: `max_subtasks` se conserva, cambia
  cuando se emite.
- Impacto de version: PATCH en la serie pre-1.0. Los campos son aditivos y la
  regla de compatibilidad de streaming ya vigente cubre su aparicion; I3
  corrige un fallo observable (exito aparente sobre cadena vacia). El numero lo
  corta el usuario en la reconciliacion (`meta POLITICA_SEMVER.md`, ADR 0030).
- Bateria ANTES de implementar, como en v0.1, v0.2 y v0.3: plan con todos los
  requisitos cubiertos (sin re-derivacion); plan con requisito huerfano que la
  segunda derivacion corrige; plan con requisito huerfano que la segunda NO
  corrige (continua y marca); plan que excede `max_subtasks` y cabe en la
  segunda; plan que excede `max_subtasks` en las dos (corte bajo I3, con codigo
  de salida y sin exito aparente); una sola re-derivacion cuando concurren I1 e
  I2; y no regresion (plan correcto a la primera, salida identica a la actual).
- Digest de conformance: cambia. Se declara el nuevo, patron de v0.2-3 y v0.3-2
  (ADR 0017).
- Paridad CLI/REST/MCP para los campos nuevos y para el codigo de salida (ADR
  0036).
- No toca `coverage_complete` ni la exactitud factual (ADR 0025, ficha
  v0.3/0003, territorio de conscience).
- Habilita, sin construirlo, el argumento de `task.run` como modo por defecto:
  hoy no lo puede ser porque sus dos modos de fallo son silenciosos. Esa
  decision de superficie es distinta y no se toma aqui.

### D-AUSENCIA: el planificador que no declara requisitos

Reconciliado 2026-08-06. Marcado con etiqueta propia para poder localizarlo y
revisarlo si el comportamiento en uso no convence.

Si la respuesta del planificador NO trae `requirements`, se trata igual que si
trajese todos sus requisitos huerfanos: dispara la unica re-derivacion y, si el
segundo intento tampoco los declara, la tarea continua con
`requirements_covered: false`.

Motivo: no anade un tercer estado ni un corte tipado nuevo, y evita que un
planificador que ignore la instruccion evada el invariante en silencio -que es
justo el modo de fallo que este ADR existe para cerrar-.

Alternativas descartadas, por si hay que volver:

- `PlanParseError`: estricto y limpio, pero mata toda tarea cuyo planificador
  no colabore, incluido un modelo pequeno que simplemente no siga el formato.
- `requirements_covered: true` por vacuidad: compatible hacia atras, pero
  convierte el invariante en opcional para quien no lo declare.

### Alcance: los dos modos (reconciliado 2026-08-06)

Los tres invariantes aplican a `pipeline` y a `coverage`. El hueco es del
planificador, no del modo: PLAN (pipeline) tiene exactamente el mismo agujero
-devuelve prompts de subtarea sin declarar que requisito atienden- y su corte
`max_subtasks` mata igual de silenciosamente (verificado: dos de las seis
ejecuciones muertas del laboratorio eran pipeline). Acotarlo a `coverage`
habria dejado el mismo defecto vivo en el modo por defecto.

Se descarta por tanto la alternativa de acotar a `coverage`, mas barata en
bateria y coherente con como ADR 0038 acoto su propio alcance, pero que deja
sin arreglar el modo que mas se usa.

### Alternativas descartadas

- **Verificar la respuesta final contra el prompt con un modelo de control**:
  revierte ADR 0025 y, segun la evidencia de laboratorio, pediria al modelo que
  fallo que se autodetecte. Es de `ia_nest_core_conscience`.
- **Cortar con error tipado cuando I1 detecta huerfanos**: mas barato y mas
  honesto, pero convierte cada plan imperfecto en una tarea perdida. Con
  `prompt.run` cubriendo lo rapido y lo atomico, `task.run` puede permitirse
  gastar una derivacion mas y entregar algo marcado antes que nada
  (decision del usuario, 2026-08-06).
- **Re-derivar hasta convergencia**: sin techo, una tarea puede no terminar; con
  techo configurable, es un parametro mas sin caso que lo pida. Una sola
  re-derivacion cubre la evidencia observada.
- **Hacer regulable el numero de re-derivaciones**: anti-entropia. No hay caso.
- **Reutilizar `max_replans` como contador**: mezcla dos cosas distintas. La
  re-planificacion de EVALUATE es un juicio sobre contenido ya producido; la
  re-derivacion de I1/I2 es una correccion estructural previa a producir nada.
  Compartir contador haria que una consumiese el presupuesto de la otra.
- **Un corte tipado nuevo para requisitos huerfanos**: no procede, porque bajo
  la decision del usuario la tarea NO corta por esa causa: continua y marca.
  El estado viaja en `requirements_covered`, no en `stop_reason`.
- **Comprobar la cobertura de requisitos con un segundo modelo**: mismo
  argumento que la primera alternativa, y ademas innecesario: si el
  planificador declara `covers`, la comprobacion es una operacion de conjuntos.

## Extension: I4, ninguna salida malformada mata la tarea (2026-08-11)

Reconciliada por el usuario el 2026-08-11. Se anade como cuarto invariante de
este mismo ADR, y no como decision aparte, porque es la MISMA doctrina que I2 e
I3 aplicada a una costura distinta: I2 dice que un limite negocia antes de
matar, I3 dice que un corte no se disfraza de exito, e I4 dice que una salida
malformada de un modelo interno tampoco mata.

### El hueco que cierra

I1, I2 e I3 gobiernan los LIMITES del orquestador. Nada gobernaba sus CONTRATOS
DE PARSEO, y ahi es donde `task.run` se estaba rompiendo.

`prompt.run` no impone ninguna forma a la salida del modelo: el texto ES la
respuesta, asi que el modelo no puede incumplir. `task.run` hace del orden de
`3 + n` llamadas por pasada e impone contrato de forma sobre TRES de ellas -la
forma del plan, la forma de `depends_on` y la palabra del evaluador; en
`coverage`, ademas, los ids del validador-. Hoy cada uno de esos contratos es
una puerta MORTAL: o el modelo emite exactamente lo esperado, o se pierde la
tarea entera.

Esa es la razon estructural de que "task run falle y prompt run no". No es que
el orquestador sea mas fragil por llamada: es que convirtio cada salida de
modelo en un contrato que mata, y tiene varios.

### La evidencia

Medida en el host de laboratorio el 2026-08-10 y el 2026-08-11 (detalle en
`local/lab/`, no versionado):

- **Forma del plan.** Ante una pregunta no separable ("la leyenda del numero 47
  en el cine"), el planificador devuelve un OBJETO suelto en vez de una lista,
  **10 de 10 veces**. `PlanParseError`, tarea perdida, de forma determinista: no
  es un fallo intermitente, ese prompt no puede funcionar.
- **Forma de `depends_on`.** En tareas secuenciales, el planificador
  referenciaba las dependencias por el TEXTO de la otra subtarea
  (`'Prepara el sistema'`), el 100% de los valores, en la mitad de los planes
  (ficha v0.3/0011, ya corregida en su capa de tolerancia).
- **Palabra del evaluador.** Pedimos "Return only one word: done, rerun, or
  replan" y el evaluador se puso a RESPONDER LA TAREA: "Para verificar si un
  servidor web esta respondiendo correctamente, puedes utilizar curl...".
  `EvaluationDecisionError`, y se tiro a la basura una respuesta combinada que
  ya estaba producida. 1 de 3 ejecuciones.

En los tres casos el modelo hizo algo RAZONABLE. El que no supo encajarlo fue el
orquestador.

### La decision

Toda llamada interna del orquestador que imponga un contrato de forma declara su
degradacion. El orden es siempre el mismo, y las dos primeras capas ya son
doctrina del repo:

1. **Tolerar** lo que tenga significado recuperable (fichas v0.3/0001, 0002 y
   0011). No se toca.
2. **Renegociar UNA vez POR ETAPA**, con el defecto explicito en la
   instruccion. Ver mas abajo la seccion "Contador por etapa", que es donde se
   fija la regla. No se anade ningun parametro de configuracion: el 1 es de
   contrato, como en I1/I2.
3. **Degradar de forma declarada**, nunca morir:
   - **plan inservible** tras renegociar -> plan de UNA subtarea que es el prompt
     integro. La tarea se comporta como un `prompt.run` caro, que es exactamente
     el desenlace correcto cuando la tarea no era separable;
   - **decision del evaluador indescifrable** tras renegociar -> se asume `done`.
     La respuesta combinada ya existe; lo conservador es parar, no destruirla;
   - **ids del validador de coverage** ilegibles -> el fragmento no acredita
     ninguna unidad y se reintenta segun `max_retries_per_unit`.
4. **Marcar** siempre. Ninguna degradacion es silenciosa (I3).

### Contador por etapa, no por tarea (reconciliado 2026-08-11)

La primera redaccion de I4 hacia que la renegociacion del EVALUADOR gastase el
mismo contador unico de re-derivacion de I1/I2. Se corrige aqui, a instancia del
usuario, porque contradecia un razonamiento que este mismo ADR ya tenia
registrado en sus alternativas descartadas: "la re-planificacion de EVALUATE es
un juicio sobre contenido ya producido; la re-derivacion de I1/I2 es una
correccion estructural previa a producir nada. Compartir contador haria que una
consumiese el presupuesto de la otra".

Regla vigente: **una renegociacion por ETAPA**, fijada en 1 por contrato.

- **Etapa PLAN**: una sola renegociacion, compartida por I1 (requisitos
  huerfanos), I2 (plan que no cabe) y I4 en su causa de FORMA del plan. Aqui
  compartir es lo correcto y el razonamiento original de I1/I2 se conserva
  intacto: son el mismo artefacto en el mismo momento, y un plan que ni cabe ni
  cubre ni parsea es UN solo plan malo.
- **Etapa EVALUATE**: renegociacion propia, independiente de la anterior.
- **Validador de coverage**: conserva la suya, que ya existe y se llama
  `max_retries_per_unit`.

Tres razones, ademas de la coherencia con el ADR:

1. Con contador unico, un hipo del planificador al principio se gasta la segunda
   oportunidad de un evaluador que falla al final. Son sucesos causalmente
   independientes, en llamadas y momentos distintos, y el comportamiento pasa a
   ser NO LOCAL: si el evaluador se reintenta o no depende de lo que ocurrio en
   otra etapa. Es dificil de razonar y dificil de probar.
2. El contador unico no tiene observable coherente. Este ADR publica
   `plan_attempts`; un reintento del evaluador no puede incrementarlo sin que el
   campo deje de significar lo que dice. Por etapa sale limpio:
   `plan_attempts` conserva su sentido y se anade `evaluation_attempts`.
3. El peor caso son DOS llamadas de recuperacion por tarea, una por etapa.
   Acotado y pequeno; no hay cascada posible con dos etapas y una cada una, que
   era lo unico que el contador unico protegia.

### Precedente interno: coverage ya lo hace

El punto 3 no inventa nada. En `coverage`, el validador YA degrada: su parseo es
tolerante y devuelve conjunto vacio en vez de lanzar, y la llamada esta envuelta
de modo que un `CoreError` marca reintento en vez de matar la tarea. I4
generaliza al PLAN y al EVALUADOR un comportamiento que una de las tres costuras
ya tenia. La asimetria era el defecto.

### Lo que NO degrada

Los errores de INFRAESTRUCTURA siguen matando: `ModelUnavailable`,
`AdapterError`, config invalida. Degradarlos ocultaria un despliegue roto detras
de respuestas de peor calidad, que es el modo de fallo mas caro de diagnosticar.
I4 cubre lo que un modelo DICE, no que el modelo este.

### Campos nuevos (aditivos)

- En el resultado de `task.run`: `degradations`, lista de degradaciones
  declaradas -etapa, causa y accion tomada-. Lista vacia cuando no hubo ninguna.
- En el resultado y en `iteration_end`: `evaluation_attempts` (1 o 2), gemelo de
  `plan_attempts` para la etapa EVALUATE.
- En `plan_ready`: `plan_source` (ADR 0040) admite el valor que declara el plan
  degradado a una subtarea.
- La CLI avisa por stderr de cada degradacion, con el patron de I3.

No se anade ningun corte tipado: una degradacion NO es un corte. La tarea
termina por merito propio, con menos orquestacion de la pedida y diciendolo.

### El riesgo que hay que vigilar, y por que el orden importa

Degradar tiene una trampa: si se hace a la primera y en silencio, `task.run` se
convierte en `prompt.run` cada vez que el planificador hipa, y nadie se entera de
que dejo de orquestar. Por eso la renegociacion va PRIMERO -para que la
degradacion sea el ultimo recurso y no el primero- y por eso el marcado es
obligatorio.

El coste tambien se declara, porque es real: una tarea degradada a una subtarea
paga planificador, subtarea, combinador y evaluador para producir lo que
`prompt.run` da en una llamada. Es la perdida de rendimiento que el usuario
acepto explicitamente al reconciliar (2026-08-11) a cambio de que no se pierda
la tarea.

### Consecuencia

- `CORE_CONTRACT.md`: `task.run` gana `degradations` y la regla de I4. El
  catalogo de cortes tipados NO crece.
- `PlanParseError` y `EvaluationDecisionError` dejan de emitirse desde
  `task.run` en los caminos que I4 cubre; siguen vigentes en la taxonomia
  (ADR 0020) y para los usos que no degradan.
- **Impacto de version: PATCH**, con el mismo criterio que este ADR aplico a
  I1-I3: campos aditivos mas la correccion de un fallo observable -tareas
  perdidas por una salida que tenia arreglo-. El numero lo corta el usuario
  (`meta POLITICA_SEMVER.md`, ADR 0030).
- **La bateria congelada de este ADR crece** antes de implementar
  (`eval/battery/v0.3/invariantes_orquestador.yaml.frozen`): plan devuelto como
  objeto suelto que la renegociacion corrige; plan devuelto como objeto suelto
  que la renegociacion NO corrige -degrada a una subtarea y lo declara-;
  evaluador con decision ilegible que la renegociacion corrige; evaluador
  ilegible que no se corrige -se asume `done` y se declara-; una sola
  renegociacion de PLAN cuando concurren I1, I2 e I4 de forma; una tarea que
  renegocia PLAN y ademas EVALUATE, para fijar que los contadores son
  INDEPENDIENTES (`plan_attempts: 2` y `evaluation_attempts: 2` a la vez);
  `ModelUnavailable` en una subtarea sigue matando la tarea (guarda de la
  frontera); y no regresion, con `degradations` vacia y ambos contadores en 1 en
  el camino sano.
- Digest de conformance: cambia, y se declara con el patron de siempre.
- Paridad CLI/REST/MCP para el campo nuevo y para el aviso.
- Se implementa junto a I1/I2 en la fase B, que sigue pendiente: extender ahora
  el ADR cuesta una pasada de implementacion en vez de dos.

### Alternativas descartadas

- **Un ADR nuevo y paralelo.** Habria dejado dos doctrinas de resiliencia del
  orquestador en documentos distintos, con dos contadores de renegociacion que
  tarde o temprano se pisan. La costura es distinta, la doctrina es la misma.
- **Un solo contador de renegociacion para toda la tarea.** Era la primera
  redaccion de I4. Mas simple de contar y con un tope duro sobre las llamadas de
  recuperacion, pero hace que una etapa se coma el presupuesto de otra, deja el
  comportamiento sin observable coherente y contradice el razonamiento que este
  ADR ya habia registrado contra compartir contadores entre PLAN y EVALUATE.
- **Degradar sin renegociar antes.** Mas simple y mas barato, pero convierte
  `task.run` en `prompt.run` al primer hipo del planificador, sin gastar el
  intento que casi siempre lo arregla.
- **Degradar en silencio, sin `degradations`.** Salida mas limpia, a cambio de
  que nadie pueda saber si la orquestacion ocurrio. Contradice I3 de frente.
- **Terminar con codigo de salida distinto de cero cuando hubo degradacion.**
  Fuerza la visibilidad, pero hace indistinguible una tarea RESUELTA con menos
  orquestacion de una tarea CORTADA sin resultado, que es la distincion que I3
  acaba de establecer. La degradacion se anuncia por stderr y por campo, no por
  codigo de salida.
- **Construir `capability.route`** (ADR 0038) para decidir antes si la tarea es
  atomica y mandarla a `prompt.run`. Es la solucion elegante, y sigue diferida:
  I4 resuelve el caso sin capacidad nueva ni clasificador adicional, que es lo
  que la regla anti-entropia pide.
- **Saltar COMBINE cuando el plan tiene una sola subtarea.** Ahorraria una
  llamada justo en el caso degradado, pero cambia el comportamiento de los planes
  de una subtarea LEGITIMOS, que hoy pasan por el combinador. Es una optimizacion
  con impacto propio: ficha aparte si se quiere, no parte de I4.
