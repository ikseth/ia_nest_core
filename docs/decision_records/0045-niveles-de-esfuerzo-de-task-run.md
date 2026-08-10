# Decision 0045: niveles de esfuerzo de task.run (effort low/medium/high)

Fecha: 2026-08-10
Estado: propuesta, pendiente de reconciliacion por el usuario
Depende de: ADR 0044 (presupuesto de tokens dimensionado por el plan)

## Contexto

Los limites de `task.run` -presupuesto, subtareas, iteraciones, replanificaciones,
tiempo- son hoy CONFIGURACION DE PROCESO: viven en el bloque `orchestration` de
`core.yaml` y son los mismos para toda peticion. Variarlos exige editar el
fichero y reiniciar.

El mismo despliegue quiere formas distintas para peticiones distintas. La
evidencia esta medida y registrada en ADR 0041: "Enumera los ocho planetas y
explica brevemente cada uno" deriva 16 unidades y necesita un techo alto; una
consulta corta en el mismo despliegue no necesita mas de tres. Hoy el operador
solo puede elegir un tamano y equivocarse en la mitad de los casos: si lo pone
bajo, mata los planes buenos (el modo de fallo del ADR 0041); si lo pone alto,
regala presupuesto a lo trivial.

ADR 0044 es lo que hace posible esta decision. Con un techo constante, un preset
solo podria decir "elige una constante mas grande", que es justo lo que 0044
descarta. Con `base + per_subtask * n`, un nivel declara algo con sentido: lo
que cuesta una unidad de trabajo y cuantas pasadas se autorizan.

## Decision

### D1: `effort` es un preset con nombre de los limites de intencion de una tarea

`task.run` acepta una entrada opcional `effort`, con vocabulario FIJO de tres
valores: `low`, `medium`, `high`. Los VALORES de cada nivel los declara el
operador en la config; el consumidor solo elige un identificador del catalogo.

`effort` es al nivel de TAREA lo que `profile` es al nivel de LLAMADA: un
paquete con nombre de parametros de ejecucion. Misma idea, dos alturas. No se
reutiliza la palabra `profile` para no confundir dos alturas distintas, ni la
palabra `mode`, que ya designa `pipeline|coverage` (ADR 0038).

### D2: que gobierna, y que NO

Gobierna los ejes de INTENCION -cuanto TRABAJO se autoriza-:

- `max_subtasks`,
- `max_iterations`,
- `max_replans`,
- `max_time_s`.

**No gobierna `token_budget`**, aunque parezca el candidato mas obvio. Bajo ADR
0044 el presupuesto ya es `base + per_subtask * n`, concedido por pasada: crece
solo cuando el nivel autoriza mas unidades y mas pasadas. Si ademas el nivel
multiplicase `per_subtask`, el crecimiento se contaria DOS VECES -cuatro veces
mas unidades y cuatro veces mas presupuesto por unidad, dieciseis veces el techo
del fan-out-.

El argumento de fondo es mas fuerte que el aritmetico: `per_subtask` no es una
POLITICA, es una MEDICION. Es lo que cuesta de verdad ejecutar una subtarea, y
lo fija el `max_tokens` del perfil, no las ganas de trabajar. Una subtarea bajo
`high` no produce una respuesta cuatro veces mas larga: el perfil la corta
igual. Multiplicarlo aflojaria el techo sin comprar ni un token de trabajo.

Por tanto: el nivel dice CUANTO trabajo se autoriza; el presupuesto lo sigue
por la formula de ADR 0044, sin que el nivel lo mencione.

**No gobierna `max_parallel`**, y esto es normativo. El paralelismo no describe
cuanto se quiere pensar: describe cuantas llamadas simultaneas aguanta la
maquina. Si el esfuerzo lo moviera, un `high` haria que el MISMO prompt fuese
peor en un portatil y mejor en el laboratorio, con el usuario creyendo que ha
pedido calidad. Ademas, los parametros de forma de la maquina son el territorio
de `ia_nest_core_pulse`, que regula "dentro de los techos del core" (ADR 0037):
si el esfuerzo tocase hilos, `pulse` y el consumidor se disputarian la misma
perilla.

`max_parallel` permanece en el bloque base de `orchestration`.

Nota sobre `max_subtasks`: subirlo en `high` es correcto (la evidencia de ADR
0041 pedia 16 unidades contra un techo de 12), pero no es "mas calidad" en
abstracto: es PERMISO PARA DESCOMPONER MAS. Descomponer de mas fragmenta una
respuesta que no es enumerable. Por eso el eje es de intencion y no de calidad
monotona, y por eso `low` bajandolo es tan legitimo como `high` subiendolo.

### D3: precedencia, en una sola regla

Lo que un nivel declara SUSTITUYE al valor de la base; lo que no declara, cae a
la base.

De esa unica regla salen tres consecuencias sin necesidad de mas reglas:

- **El bloque base ES el nivel `medium`.** No hay que declararlo, y no existe un
  cuarto estado "sin especificar".
- Un nivel declarado a medias es valido: hereda el resto.
- Un nivel NO declarado en la config resuelve a la base. No es un error: es un
  nivel vacio.

### D4: el operador declara, el consumidor elige un id

Por el cable de `task.run` viaja un identificador (`low|medium|high`), nunca
cifras. Un consumidor no puede inventarse un presupuesto.

Es la misma forma que ya tienen los dominios -el operador los declara, el router
elige uno- y preserva el reparto de responsabilidades del ente: el core sostiene
los techos y `pulse` regula dentro de ellos (ADR 0037). Si el consumidor pudiese
mandar numeros, no habria techo que sostener.

Un `effort` fuera del vocabulario es error tipado
`CoreError("ConfigError", ..., "effort")`, igual que hoy un `mode` invalido.

### D5: el nivel por defecto es `medium`, y es configurable

`orchestration.default_effort` declara el nivel que se aplica cuando la peticion
no lo indica. Valor de fabrica: `medium`, es decir el bloque base.

Se descarta `low` como valor de fabrica por dos razones:

1. **Compatibilidad.** Con `medium` por defecto, una config existente sin
   `effort` ni `default_effort` se comporta EXACTAMENTE igual que antes de esta
   decision. Con `low`, toda config existente cambiaria de comportamiento en
   silencio -menos iteraciones, menos presupuesto- sin que nadie hubiera tocado
   nada.
2. **Es el fallo que se acaba de corregir.** El modo de fallo medido no es el
   desbocamiento sino la infra-provision: 4096 fijos que cortan una pasada sana
   (ADR 0044). Enviar `low` de fabrica reintroduciria "task.run corta demasiado
   pronto" como experiencia por defecto justo despues de arreglarla.

El operador que quiera ser conservador escribe `default_effort: low`. Esa es una
decision suya y explicita, no una nuestra por omision.

### D6: alcance

- Aplica a los DOS modos (`pipeline` y `coverage`). Los limites que gobierna son
  comunes a ambos.
- NO se extiende a `prompt.run` ni a `reasoning.run`: ahi el paquete de
  parametros con nombre ya existe y se llama `profile`.
- La bateria de evaluacion fija el `effort` de cada caso EXPLICITAMENTE. Si un
  caso lo dejase implicito, el digest de conformance dejaria de ser reproducible
  en cuanto alguien cambiase `default_effort`.

### D7: como se fijan los tres niveles

`low` es el ANCLA y se MIDE; `medium` y `high` se DERIVAN de el por escalones.

**El ancla.** `low` es el minimo que no corta la tarea mas pequena que merece
`task.run`. Se calibra en laboratorio: se mide el consumo real de una tarea de
dos o tres subtareas y se fija `low` por encima del percentil alto observado.

Precision importante sobre el caso de calibracion: el suelo se mide contra la
TAREA mas pequena, no contra una pregunta sencilla. Una pregunta sencilla no
deberia estar usando `task.run` -para eso esta `prompt.run`, y esa frontera es
explicita en `CORE_CONTRACT.md`-. Calibrar `low` contra un prompt atomico seria
calibrarlo para un caso que no le corresponde.

**Los escalones.** La forma es exponencial, x2 por escalon, pero NO uniforme en
los cuatro ejes, y las excepciones son la parte importante:

| eje | low | medium | high | escalon |
|---|---|---|---|---|
| `max_subtasks` | 3 | 6 | 12 | x2 |
| `max_iterations` | 1 | 2 | 4 | x2 |
| `max_replans` | 0 | 1 | 2 | a mano |
| `max_time_s` | 30 | 120 | 480 | x4 |

`max_replans` no admite multiplicador: su suelo correcto es 0 -un nivel para
tareas pequenas no replanifica- y 0 multiplicado sigue siendo 0. Se fija a mano.

`max_time_s` escala mas fuerte que el resto, y esta es la consecuencia menos
evidente de la decision. Las pasadas son ADITIVAS (el bucle acota por
`max_iterations` mas `max_replans`), pero el gasto COMPONE, porque cada pasada
recorre `n` unidades:

- `low`: n=3, del orden de 1 pasada, unas 6 llamadas;
- `high`: n=12, del orden de 4 pasadas, unas 60 llamadas.

Son DIEZ veces mas llamadas entre `low` y `high`, no cuatro. Con `max_parallel`
en 2 eso es la diferencia entre unos 20 segundos y unos 200 en el laboratorio.
Si `max_time_s` escalase x2 como los demas ejes, el reloj se convertiria en el
limite EFECTIVO de `high`: el nivel autorizaria mas trabajo y moriria por tiempo
antes de hacerlo, con lo que el nivel alto no serviria para nada. El escalon del
tiempo compensa la composicion del resto.

Los numeros de la tabla son punto de partida, no contrato: los fija la misma
puerta de laboratorio que calibra los defaults de ADR 0044, y manda la medida.

### Forma en la config

```yaml
orchestration:
  planner: { model: ..., profile: default }
  combiner: { model: ..., profile: default }
  max_parallel: 2                                  # maquina: fuera del esfuerzo
  token_budget: { base: 4096, per_subtask: 2048 }  # medicion (ADR 0044), no nivel
  max_subtasks: 6                                  # el bloque base ES medium
  max_iterations: 2
  max_replans: 1
  max_time_s: 120
  default_effort: medium
  effort:
    low:
      max_subtasks: 3
      max_iterations: 1
      max_replans: 0
      max_time_s: 30
    high:
      max_subtasks: 12
      max_iterations: 4
      max_replans: 2
      max_time_s: 480
```

Los niveles no mencionan `token_budget` (D2) ni `max_parallel` (D2). `medium` no
se declara: es el bloque base.

### Campos nuevos (aditivos)

- Entrada de `task.run`: `effort` opcional. CLI `--effort {low,medium,high}`,
  campo equivalente en REST y argumento en MCP (paridad, ADR 0036).
- Resultado: `params` publica el `effort` resuelto junto a los parametros
  efectivos, que ya es el patron ("parametros efectivos" de `CORE_CONTRACT.md`).
- Config: `orchestration.effort` y `orchestration.default_effort`, ambos
  opcionales.

La columna de correlacion en telemetria CSV no se abre aqui: viaja con el
trabajo pendiente de telemetria (punto B3), que rompe esquema y tiene su propia
decision. En JSONL el `effort` resuelto sale ya, dentro de `params`.

## Motivo

### Por que es core y no una herramienta externa

La regla anti-entropia obliga a preguntarlo. El criterio de
`IA_NEST_CORE_CONTEXT.md` es si la capacidad necesita el estado interno del
core para funcionar.

Lo necesita: los limites de `task.run` son hoy configuracion de proceso, y
variarlos por peticion desde fuera exigiria recargar `core.yaml` en cada
llamada. No hay forma de que una capa superior lo haga sin reimplementar la
orquestacion. Ademas, D4 es precisamente la razon por la que NO puede vivir
fuera: el sentido de la pieza es que los techos los sostenga el core.

### Por que vocabulario fijo y valores configurables

La alternativa natural es un catalogo abierto donde el operador nombre sus
niveles (`rapido`, `exhaustivo`...). Es mas flexible y mas afin a como se
declaran dominios y perfiles.

Se descarta porque los consumidores del ente se conectan por CONTRATO
(`ia_nest_agents`, `ia_nest_web`, ADR 0033). Con catalogo abierto, un agente no
puede confiar en que `alto` exista en el despliegue de al lado: el nombre deja
de ser contrato y pasa a ser configuracion local, y cada consumidor tendria que
descubrir el catalogo antes de pedir nada.

Vocabulario fijo con valores calibrables da las dos cosas: el nombre es
portable, la magnitud es local. Es la logica de las tallas de camiseta.

Tres niveles y no cinco: con cuatro o mas, dos de ellos acaban con numeros casi
identicos y el consumidor no sabe cual pedir. Tres se calibran y se distinguen.

### Lo que esto NO arregla

Un nivel de esfuerzo no mejora al planificador. Los `PlanParseError` estocasticos
y las dependencias invalidas son un problema de robustez del parseo y del
prompt de planificacion, y mas presupuesto no convierte un JSON malformado en un
plan valido.

Queda escrito porque el riesgo de esta pieza es que se convierta en la respuesta
a todo -"va mal, ponlo en high"- y tape el trabajo de robustez en lugar de
sustituirlo. `high` compra mas trabajo, no mas acierto.

### El tamiz

- **Resiliencia**: el operador deja de tener que elegir un unico tamano que
  acierte en todos los casos, que es lo que produjo la evidencia de ADR 0041.
- **Escalabilidad**: `task.run` pasa a ser utilizable desde lo trivial hasta lo
  costoso sin tocar la config ni reiniciar.
- **Modularidad**: ningun mecanismo nuevo en el motor; un resolutor de
  precedencia sobre limites que ya existen. Y una frontera limpia con `pulse`:
  intencion aqui, maquina alli.
- **Sencillez**: una entrada, tres valores, una regla de precedencia. El nivel
  medio no se declara.
- **Estrategia**: da al consumidor un control identificable y estable, y deja
  intacto el reparto de techos entre core y `pulse`.

## Consecuencia

- `CORE_CONTRACT.md`: `task.run` gana la entrada opcional `effort` y publica el
  nivel resuelto en sus parametros efectivos.
- Esquema de config: `orchestration.effort` y `orchestration.default_effort`,
  aditivos y opcionales.
- **Impacto de version: MINOR** (adicion compatible: entrada opcional nueva,
  seccion de config nueva, campo nuevo en el resultado; nada existente cambia de
  comportamiento). Se propone entregarla en la MISMA linea MINOR que ADR 0044,
  con una sola bateria: sin 0044 esta decision no tiene sustancia, y separarlas
  obliga a calibrar numeros dos veces. El numero lo corta el usuario
  (`meta POLITICA_SEMVER.md`, ADR 0030).
- **Digest de conformance: cambia**, por los casos nuevos y por la fijacion
  explicita de `effort` en los casos existentes. Se declara junto al de 0044.
- Bateria ANTES de implementar:
  1. sin `effort` y sin `default_effort`: salida identica a la base (no
     regresion; es la guarda de compatibilidad de D5);
  2. `--effort low` y `--effort high`: los parametros efectivos del resultado
     son los del nivel;
  3. un plan que `low` cortaria por `max_subtasks` termina con `high`;
  4. nivel declarado a medias: los campos ausentes caen a la base;
  5. nivel no declarado en la config: resuelve a la base, sin error;
  6. `default_effort: low`: sin bandera se aplica `low`;
  7. `effort` fuera del vocabulario: `ConfigError` con `field: effort` y codigo
     de salida distinto de cero;
  8. el nivel aplica igual en `mode=coverage`;
  9. `max_parallel` NO cambia con el nivel (guarda de D2);
  10. el `token_budget` resuelto es el MISMO en los tres niveles para un mismo
      `n` (guarda de D2: el nivel no toca la medicion, solo el trabajo
      autorizado);
  11. paridad CLI/REST/MCP del campo y del nivel resuelto.
- Los valores POR DEFECTO del esquema y de las dos plantillas se recalibran en
  la misma pasada (`max_subtasks`, `max_iterations`, `max_replans`,
  `max_time_s` pasan a los de `medium` en D7). Es un cambio deliberado y
  declarado, no un efecto del mecanismo de esfuerzo: la garantia de
  compatibilidad de D5 dice que una config que declara sus limites se comporta
  igual que antes, no que los defaults de fabrica se congelen. Las dos
  plantillas declaran todos sus limites de forma explicita, asi que ninguna
  cambia de comportamiento sin que se vea en el diff.
- Manual: `docs/manual/cli.md` y `docs/manual/configuracion.md` documentan la
  bandera, la seccion y la regla de precedencia. (Ambos tienen ya deuda abierta
  por la linea del router; conviene saldarla en la misma pasada.)
- No toca `prompt.run`, `reasoning.run`, `profiles` ni `max_parallel`.

## Punto a reconciliar

**Los limites propios de `coverage` dentro de un nivel.** La propuesta abre
`max_retries_per_unit` y `max_chunks` -son eje de intencion: cuanto se insiste y
cuantos fragmentos se autorizan- y deja FUERA `units_per_chunk`, que decide
cuanto se mete en una sola llamada de generacion y por tanto empuja la ventana
del modelo, mas cerca de un parametro de maquina que de intencion.

Alternativa mas simple, por si se prefiere: que ningun limite propio de coverage
entre en el nivel, y que `effort` gobierne solo los cuatro limites comunes. Menos
superficie, a cambio de que `high` en coverage no pueda insistir mas por unidad.

## Alternativas descartadas

- **Catalogo abierto de niveles** declarado por el operador: mas flexible y mas
  afin al resto de la config, pero rompe la portabilidad del nombre para los
  consumidores que se conectan por contrato (ver Motivo).
- **Cinco o mas niveles (`light/medium/high/XXL`...)**: vocabulario comercial y,
  en la practica, dos niveles indistinguibles.
- **Que el nivel gobierne `max_parallel`**: mezcla intencion con maquina, hace
  que el mismo prompt rinda distinto por hardware bajo el mismo nombre, e invade
  el territorio de `pulse` (ADR 0037).
- **Que el consumidor mande cifras en vez de un identificador**: maxima
  flexibilidad, pero el core deja de sostener techos y `pulse` se queda sin
  techo dentro del cual regular.
- **Reutilizar la palabra `profile` para el nivel de tarea**: no anade
  vocabulario, pero confunde dos alturas distintas -parametros de una llamada
  frente a limites de una orquestacion- en un mismo termino.
- **Reutilizar `mode`**: ya designa `pipeline|coverage` (ADR 0038); dos "modos"
  ortogonales en la misma capacidad es la peor opcion de nombres disponible.
- **`low` como nivel por defecto de fabrica**: mas conservador, pero cambia en
  silencio el comportamiento de toda config existente y reintroduce por defecto
  la infra-provision que ADR 0044 corrige (D5).
- **Extender `effort` a `prompt.run` y `reasoning.run`**: simetria aparente; ahi
  el paquete con nombre ya existe (`profile`) y duplicarlo seria entropia.
- **Hacer el numero de niveles configurable**: perilla sobre perilla, sin caso.
- **Que el nivel multiplique tambien `token_budget`**: es la lectura intuitiva
  de "nivel de esfuerzo", y es la que traia el primer borrador de esta decision.
  Se descarta por doble contabilidad y porque `per_subtask` es una medicion y no
  una politica (D2).
- **Declarar en la config solo `low` y un factor, y derivar `medium`/`high` en
  codigo**: menos numeros y una sola fuente de verdad. Se descarta porque el
  factor NO es uniforme entre ejes -`max_replans` no admite multiplicador y
  `max_time_s` necesita uno mayor (D7)-, asi que la derivacion automatica seria
  falsa en dos de los cuatro ejes. La forma exponencial se conserva como
  DOCTRINA para elegir los numeros, escrita en D7; las tres filas quedan
  explicitas en la config, donde el operador las ve.
- **Escalar `max_time_s` al mismo ritmo que el resto**: coherente de aspecto,
  pero convierte el reloj en el limite efectivo de `high` y vacia el nivel alto
  de contenido (D7).
