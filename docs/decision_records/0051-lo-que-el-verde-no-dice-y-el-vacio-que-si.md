# Decision 0051: lo que el verde del core no dice, y el vacio que si puede declarar

Fecha: 2026-08-22
Estado: reconciliado por el usuario (2026-08-22)

Depende de: ADR 0036 (contrato de `task.run`), ADR 0041 (criterios de gestion de
tareas), ADR 0042 (saneo del canal de razonamiento en origen), ADR 0044
(presupuesto), ADR 0045 (niveles de esfuerzo), ADR 0047 y ADR 0048 (plan
suministrado), ADR 0034 y ADR 0037 (fronteras de conscience y pulse).

Origen: hallazgos medidos por `ia_nest_extended` el 2026-08-22 (issue #36, brief
`ia_nest_meta/docs/handoff/avisos_al_core_desde_extended_2026-08-22.md`) y el
2026-08-18. No son Change Requests: ninguno pide capacidad ni cambio de
contrato. Esta decision DISPONE sobre los tres, y rechaza dos cosas por escrito.

## Contexto

### Lo primero: cuatro sospechas de seis no sobrevivieron a la medida

El brief que origina este ADR empieza retirando dos avisos anteriores. Se habian
medido sobre el `config/core.lab.example.yaml` publicado -seis dominios, sin
`cultura`, `max_tokens: 512` para todos- y con el roster real de 19 dominios
desaparecen: el planificador concuerda con `domain.route` en 22 de 25 subtareas
(88%, y las tres discrepancias son vecindad semantica), y la tarea que no
convergia converge en una iteracion y 33 s.

Se recoge aqui, y no como nota al pie, porque **"el planificador enruta mal" y
"`task.run` no converge" quedan MEDIDAS COMO FALSAS**. Quien las vuelva a
levantar, que las mida antes.

### Lo que queda en pie, y lo que la medida propia le anadio

De los tres hallazgos vivos, dos apuntan al mismo sitio sin saberlo:

- el gate da verde a respuestas falsas (4 pasadas, 4 veces `task_done`,
  `degradations` vacio, contenido falso las cuatro);
- el ejemplo publicado sirve de fabrica el fallo que su propio comentario
  describe: el dominio `razonamiento` con un modelo de razonamiento y un perfil
  de 512 tokens produce subtareas con `finish_reason: length` y cadena vacia,
  "y el combinador integra el vacio como si fuera un resultado".

Esa ultima frase es lo que se fue a medir. No en el laboratorio -no era
alcanzable el 2026-08-22- sino en un banco local que emite POR EL CABLE lo mismo
que emite un modelo de razonamiento truncado: `<think>` sin cerrar y
`finish_reason: length`, que ADR 0042 sanea dejando cadena vacia. Adaptador
real, HTTP real, CLI real, sin GPU. Se declara lo que es: un banco, no el
ejemplo publicado contra un modelo real.

Medido, tres pasadas por brazo:

    una subtarea vacia de dos    stop=task_done  degradations=[]  covered=True
    LAS DOS subtareas vacias     stop=task_done  degradations=[]  covered=True

Con **cero contenido producido**, el core entrega una respuesta final, la declara
`task_done`, no declara ninguna degradacion y afirma que los requisitos estan
cubiertos. Las cuatro lineas del gate -incluida la cuarta que el brief del 18
propuso- salen en verde.

Y el vacio viaja al combinador como si fuera un resultado:

    Results: [{"index": 0, "prompt": "...", "response": "",
               "finish_reason": "length", ...}, ...]

El dato esta en el payload. Nadie lo mira. El combinador, ademas, tiene prohibido
por su propio prompt mirarlo: *"Do not decide which version is true or verify any
claim"*.

Esto reencuadra los dos hallazgos. **El ejemplo publicado no es la enfermedad:
es el sintoma que la destapo.** El core integra el vacio y lo declara sano con
cualquier configuracion. La cobertura tampoco protege: `requirements_covered`
dice que una subtarea RECLAMO el requisito, no que lo respondiera.

## Decision

### D1. El verde de `task.run` es mecanico, y el contrato lo dice

`task_done` significa "el bucle termino sin chocar con ningun limite y el
evaluador acepto". `degradations` vacio significa "no hubo repliegue ni perdida
declarada". `requirements_covered` significa "cada requisito tiene al menos una
subtarea que dijo cubrirlo". **Ninguna de las tres afirma que la respuesta sea
cierta, ni siquiera que tenga contenido.**

Hasta hoy eso era verdad y no estaba escrito, asi que cada capa lo aprendia
midiendo. Se escribe en `CORE_CONTRACT.md`, donde el consumidor lo lee antes de
construir encima.

### D2. El core no verifica veracidad, y no va a hacerlo

Se rechaza, explicitamente, anadir al core cualquier senal de veracidad. No es
una limitacion que haya que corregir: es la frontera.

- Verificar exige una fuente de verdad. El core no tiene ninguna, y no la
  tendra: RAG, memoria y datos web son no-objetivos declarados
  (`IA_NEST_CORE_CONTEXT.md`) y viven en `ia_nest_extended` (ADR 0031).
- El control deliberado sobre lo que se responde es de `ia_nest_core_conscience`
  (ADR 0034). Meter un verificador aqui duplicaria esa capa dentro del motor.
- Un evaluador que juzga con el mismo modelo, el mismo contexto y sin fuente no
  verifica: opina. Subirle el listado no lo convierte en verificador, lo
  convierte en un opinador mas caro.

El core, por tanto, no promete respuestas ciertas. Promete decir la verdad sobre
COMO las produjo. Lo que D3 corrige es que hoy no la dice entera.

### D3. El core declara el vacio que si puede ver

Hay una diferencia que el core si distingue sin ninguna fuente de verdad: una
subtarea que produjo texto y una que no produjo nada. Hoy las trata igual. Tres
reglas, en `mode=pipeline`:

- **R1, declarar.** Una subtarea cuya respuesta saneada queda vacia emite la
  degradacion `{stage: fanout, reason: empty_subtask_output, action:
  excluded_from_combine, subtask: "<indice>"}`, una por subtarea afectada.
  Degradacion y no corte: se conserva lo ya producido, como manda la regla de
  degradacion declarada de ADR 0041.
- **R2, no combinar el vacio.** Las contribuciones vacias no entran en el payload
  del combinador. No son resultados; pedir que se combine un hueco es invitar a
  rellenarlo.
- **R3, no fabricar respuesta de la nada.** Si NINGUNA subtarea produjo
  contenido, el core no llama al combinador: la respuesta combinada es vacia y
  la degradacion dice por que. No se inventa un corte nuevo para el caso, porque
  el precedente del propio core es `prompt.run`, que devuelve la respuesta vacia
  del modelo con su `finish_reason` y sin ceremonia. A partir de ahi el bucle
  hace lo suyo: EVALUATE ve una respuesta vacia y decide.

Lo que NO se declara: `finish_reason: length` con texto no vacio. En `pipeline`
tocar techo es el regimen normal -el contrato ya dice que la respuesta esta
acotada por el `max_tokens` del combinador-, asi que convertirlo en degradacion
llenaria el canal de falsos positivos y lo volveria inutil. La senal es el
VACIO, que es inequivoco.

Honestidad sobre el alcance de R2 y R3: se justifican por no pedirle a un modelo
que combine nada, no por una reduccion de fabulacion medida. Esa medida es
criterio de salida de su fase, no premisa de esta decision.

### D4. Ningun sistema es su propio criterio de aceptacion

El gate de fase del core mira `degradations`, `requirements_covered`,
`params.effort` y -desde el brief del 18- `stop_reason`. Las cuatro son senales
MECANICAS emitidas por el propio sistema que se esta evaluando. Sirven para
cerrar una fase que afirma "la maquinaria hace lo que dice"; **no sirven para
cerrar una fase que afirma algo sobre la CALIDAD de la respuesta.**

Regla, aplicable a los criterios de salida del PLAN a partir de hoy:

- La cuarta linea, `stop_reason == task_done`, se adopta. Sigue siendo buena
  idea; simplemente no basta sola.
- Una fase cuya afirmacion sea sobre el contenido de las respuestas necesita un
  CONTROL externo a las senales del core: contraste contra `prompt.run` sobre la
  misma pregunta -que es como extended encontro esto: sin trocear, las respuestas
  salieron correctas-, o casos de respuesta conocida con clave, verificados
  fuera del evaluador del core.
- El evaluador del core no puede ser el criterio de aceptacion del core.

Es la misma leccion que este repo ya pago dos veces, un nivel mas arriba: una
bateria de comprobaciones de forma no detecta que esta midiendo el binario
equivocado (2026-08-20), y una verificacion que necesita que el operador haga
algo a mano antes no es una verificacion (2026-08-20). Ahora: un sistema no
detecta con sus propias senales que su respuesta es falsa.

### D5. La inestabilidad del plan NO es un defecto del core

Se rechaza como defecto. Que el mismo prompt con el mismo `effort` de 4, 16, 4 y
4 subtareas es lo que hace un modelo de lenguaje muestreado: el plan lo emite un
modelo, con el perfil que declara el operador.

Lo que el core debia comprobar es si la palanca existe, y existe. Medido por el
cable contra el banco: los parametros del perfil llegan al backend tal cual,
incluidas claves que el core no modela.

    stub-planner  {"temperature": 0.0, "max_tokens": 1024, "top_p": 1.0, "seed": 7}

`config.validate` acepta el perfil. Un planificador determinista es config del
operador, hoy, sin tocar el core.

Se rechaza ademas, por escrito:

- **Llevar `seed` o cualquier control de muestreo al contrato publico.** Seria un
  eje de MAQUINA, y ADR 0045 los dejo fuera del nivel de esfuerzo a proposito: por
  el cable viaja el identificador del nivel, nunca cifras. El hogar de los
  parametros de muestreo es el perfil, que ya funciona y ya es declarativo.
- **Que el core acote la varianza del plan por su cuenta** (estrechar
  `max_subtasks` efectivo, reintentar planes "anomalos"). Es logica implicita en
  el nucleo contra el principio 2, y el core es agnostico en modelos (ADR 0043).
  Los limites de tamano y coste ya tienen sitio declarado: `max_subtasks`,
  `token_budget` y los niveles de `effort`, con su corte tipado.

Y una via que ya existe y responde a la parte legitima del aviso -que la medida
sobre `task.run` sea reproducible-: **congelar el plan**. `task.plan` devuelve un
plan que `task.run` acepta tal cual (ADR 0040, 0047, 0048). Quien quiera medir
`task.run` sin que el planificador le mueva el suelo, planifica una vez y ejecuta
N veces ese plan. La capacidad se construyo para enriquecer, y sirve igual para
medir.

### D6. El ejemplo publicado se corrige

Aceptado sin reservas, y es el mas barato. Detalle y criterios en
[ficha v0.4/0009](../fixes/v0.4/0009-el-ejemplo-publicado-sirve-su-propio-fallo.md).

## Impacto de version

PATCH. R1 anade un valor al vocabulario de `degradations`, que es una lista ya
publicada y aditiva; R2 y R3 corrigen un comportamiento observable sin cambiar
ninguna forma. Nada se quita ni se renombra.

Aviso a quien consuma: un gate que exige `degradations == []` empezara a fallar
en ejecuciones que antes salian verdes. Es el efecto buscado, y es el mismo
patron que cuando el gate gano su segunda linea.

## Puntos abiertos

Dos medidas quedan pendientes de laboratorio, y se declaran como criterio de
salida de sus fases en el PLAN, no como supuestos de esta decision:

1. Que un perfil de planificador con `temperature: 0.0` (y `seed`, si el backend
   lo honra) colapse de verdad la varianza del tamano del plan con modelo real.
   Medido esta que el parametro VIAJA; no que el backend obedezca.
2. Que el ejemplo corregido de la ficha 0009 deje de producir cadena vacia en el
   dominio `razonamiento` con el modelo que declara.
