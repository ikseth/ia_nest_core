# Decision 0041: criterios de gestion de tareas del orquestador (adecuacion semantica, presupuesto y cortes no silenciosos)

Fecha: 2026-08-06
Estado: reconciliado por el usuario (2026-08-06)

## Decision

`task.run` incorpora tres invariantes que el orquestador comprueba sobre su
PROPIO estado (plan, ledger, presupuesto), sin que ningun modelo juzgue a otro
modelo. Aplican a los dos modos (`pipeline` y `coverage`).

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
