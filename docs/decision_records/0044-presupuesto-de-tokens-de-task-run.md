# Decision 0044: el presupuesto de tokens de task.run lo dimensiona el plan, y decide la proxima pasada

Fecha: 2026-08-10
Estado: reconciliado por el usuario (2026-08-10)

## Contexto: lo que hay hoy, y por que contradice el ADR 0008

### Un nombre, tres significados

`max_context_tokens` designa hoy tres cosas distintas:

- En `profiles`: el presupuesto ACUMULADO del bucle de `reasoning.run`
  (`reasoning_runtime.py`), que es la semantica del ADR 0008. Es inerte para
  `prompt.run`, y esta explicitamente bloqueado para que no viaje al backend
  como parametro (`openai_compatible._public_params`).
- En `orchestration`: el gasto ACUMULADO de la tarea entera -planificador,
  subtareas, combinador, evaluador, entradas y salidas, incluidas las llamadas
  paralelas- comprobado en `TaskRuntime._limit_reason`.
- Como nombre: una ventana de contexto. Ninguna de las dos acepciones anteriores
  vigila una ventana. Ninguna llamada individual esta protegida de desbordar la
  suya.

ADR 0008 fija que el presupuesto de contexto es "rendimiento y estabilidad de la
entidad simulada, NO de coste/pago (los modelos son locales)", y que el bucle
"nunca desborda la ventana de forma silenciosa". El campo de `orchestration` es
lo contrario de ambas frases: es un tope de GASTO agregado, con nombre de
ventana, que no impide ningun desbordamiento.

Esa semantica nunca se decidio. Entro por inferencia en una ficha de correccion,
v0.2/0003, que la describe como "la ya implicita en el codigo". Era un andamio,
igual que el filtro de keywords del router lo fue (ADR 0043).

### El techo no crece con el plan, que es lo que task.run existe para hacer

Una pasada de `pipeline` consume `3 + n` llamadas: planificador, `n` subtareas,
combinador y evaluador; con ADR 0041 (I1/I2) puede haber una derivacion mas.
Ademas la ENTRADA del combinador crece con `n`, porque recibe el JSON integro de
cada registro de subtarea (enunciado y respuesta). El consumo es, por tanto,
creciente en `n` por dos vias a la vez, mientras el techo es una constante.

Con los valores por defecto que publican el esquema y las DOS plantillas
(`max_tokens: 512` de perfil, `max_subtasks: 4`, presupuesto 4096):

- solo las salidas de una pasada sana son 7 x 512 = 3584;
- la entrada del combinador aporta del orden de 4 x 512 = 2048 mas;
- mas las entradas de planificador, subtareas y evaluador.

Es decir: **una pasada correcta de cuatro subtareas no cabe en el presupuesto
por construccion**, y `max_iterations: 2` es inalcanzable: la segunda pasada
nunca es pagable. Los limites que enviamos por defecto son mutuamente
incoherentes.

Por que no se vio antes: la medida de laboratorio disponible (2026-07-23, ficha
v0.2/0003) es de UNA subtarea con respuestas cortas, 798 tokens acumulados. Con
una subtarea cabe de sobra. El defecto aparece justo cuando la tarea se
descompone, que es el caso de uso de la capacidad.

### El techo gana al merito

En `TaskRuntime.stream` el limite se evalua ANTES de mirar la decision del
evaluador. Una tarea que el evaluador dio por `done` sale con
`stop_reason = max_context_tokens`; la CLI imprime "Tarea cortada" y termina con
codigo 1 (regla I3 de ADR 0041, implantada en la fase A).

No es una hipotesis: el test `test_task_runtime_limits_real_accumulated_tokens_
and_traces_them` guioniza el evaluador con `"done"` y AFIRMA como correcto que
el resultado sea `max_context_tokens`. La expectativa equivocada esta congelada
en la suite.

Esto explica una parte del sintoma "task run falla mucho mientras prompt run va
bien": no solo se corta lo que deberia continuar, sino que se presenta como
fallo lo que si termino.

### Dos modos, dos limites para el mismo trabajo

`coverage` usa `coverage.max_total_tokens` (16384, comprobado al inicio de cada
ciclo) e IGNORA `max_context_tokens`. `pipeline` usa `max_context_tokens` (4096,
comprobado al final de cada iteracion). Mismo concepto, dos nombres, cuatro
veces de diferencia y dos puntos de comprobacion distintos. El nombre correcto
-el que dice lo que mide- es el del modo que llego despues.

## Decision

### D1: el presupuesto decide la PROXIMA pasada; nunca mutila la que esta en curso

Una pasada -PLAN, FAN-OUT, COMBINE, EVALUATE en `pipeline`; un ciclo de chunks
en `coverage`- se termina siempre. El presupuesto se comprueba en los limites
entre pasadas y responde a una sola pregunta: *se empieza otra*.

Consecuencias directas, todas deseables:

- Las llamadas en vuelo del fan-out nunca se abandonan a medias.
- Nunca se corta entre FAN-OUT y COMBINE, que devolveria subtareas sin respuesta
  combinada, es decir el modo de fallo que I3 existe para cerrar.
- **El merito gana al techo**: si el evaluador dice `done` (o la cobertura queda
  completa), no hay proxima pasada que vetar y el corte es `task_done`, aunque el
  gasto haya superado el presupuesto. `task_done` sigue reservado a la
  terminacion por merito propio (ADR 0041, I3), y agotar el presupuesto DESPUES
  de terminar bien no es un corte: no hay nada que cortar.
- Un sobrepaso dentro de una pasada se registra, no se castiga; el presupuesto
  es una decision sobre el futuro, no un juicio retroactivo sobre lo ya hecho.

### D2: el plan dimensiona el presupuesto

El presupuesto efectivo se calcula cuando se conoce el plan:

```
concesion_de_la_pasada = base + per_subtask * n_unidades
```

Se CONCEDE en cada `plan_ready` y se ACUMULA; el gasto acumulado de la tarea se
mide contra la suma de concesiones. Una pasada que gasta menos deja credito para
la siguiente, que es como se comporta un presupuesto de verdad.

Reglas de concesion:

- Una re-derivacion de I1/I2 (ADR 0041) gasta de la concesion en curso; no gana
  una nueva. Es una correccion del plan de esta pasada, no una pasada mas. El
  valor de `base` cuenta con ello.
- Una re-planificacion de EVALUATE (`replan`) y una nueva iteracion (`rerun`) SI
  conceden, porque son trabajo nuevo autorizado por sus propios contadores.
- En `coverage`, la derivacion unica concede
  `base + per_subtask * n_unidades * (1 + max_retries_per_unit)`: los reintentos
  por unidad son gasto autorizado por contrato, y un presupuesto que los ignora
  vuelve a mentir.

El total sigue acotado sin multiplicar perillas, porque `max_subtasks`,
`max_iterations` y `max_replans` ya acotan cuantas concesiones puede haber. Cada
limite gobierna su propio eje.

### D3: un nombre, un significado

- `max_context_tokens` SALE de la seccion `orchestration`. Se conserva en
  `profiles` con su sentido de ADR 0008 (bucle de `reasoning.run`), intacto. Si
  aparece en `orchestration` en una config antigua, se ignora, como
  `routing_rules` (ADR 0043).
- Nueva seccion aditiva `orchestration.token_budget`, con `base` y
  `per_subtask`. Aplica a los dos modos.
- `coverage.max_total_tokens` se retira: el presupuesto de coverage pasa a
  calcularse por D2. Se ignora si aparece.
- El corte tipado de `task.run` por presupuesto pasa a ser `max_total_tokens` en
  LOS DOS MODOS. `max_context_tokens` desaparece del catalogo de cortes de
  `task.run`; sigue vigente en `reasoning.run`, que no se toca.
- La ventana por llamada NO se predice: se OBSERVA. El core no estima tokens
  antes de enviar -haria falta un tokenizador por backend, contra el caracter
  backend-agnostico del ADR 0003, y seria falsa precision-. La senal es
  `finish_reason=length`, que ya se transporta (ficha v0.2/0002) y que `coverage`
  ya trata como senal de continuacion. Se hace explicito en el contrato: `length`
  en cualquier llamada de orquestacion queda visible en el registro de subtarea.
  Asi se cumple el "nunca de forma silenciosa" del ADR 0008 por observacion, que
  es lo unico que el core puede acreditar honestamente.

### D4: campos nuevos (aditivos)

- En `plan_ready`: `token_budget_granted` (concesion de esta pasada) y
  `token_budget_total` (suma acumulada).
- En `params` del resultado: `token_budget` (`base`, `per_subtask`) sustituye a
  `max_context_tokens`.
- En la traza: `token_budget_total`, junto a los `tokens_in`/`tokens_out` que ya
  estan.

### D5: valores por defecto, y como se fijan

El ADR fija la FORMA y la regla de comprobacion. Los numeros se calibran en el
laboratorio contra telemetria medida, no se adivinan aqui.

La calibracion se ejecuto el 2026-08-11 y el 2026-08-12 (detalle en
`local/lab/`, no versionado): dos campanas de tamano de plan controlado con dos
perfiles, mas dos rebanadas de salida larga en los dos modos. **Manda la medida**,
como este apartado dejo dicho, y la medida corrigio dos cosas.

**Correccion 1: `base` NO es un coste fijo de maquinaria.** El borrador de este
apartado describia `base` como lo que cuestan planificador, combinador y
evaluador, dando a entender una constante. Medido, esa maquinaria va de 632
tokens con `n=1` a 3934 con `n=8`, porque el combinador ingiere TODOS los
resultados de subtarea y el evaluador ingiere el combinado. El ajuste por
minimos cuadrados sobre el total da un intercepto de 37 a 151 tokens: **`base`
es practicamente cero y todo escala con `n`**.

La FORMULA sobrevive intacta, porque D2 ya definia `per_subtask` como "entrada y
salida de la subtarea MAS su contribucion a la entrada del combinador": el
crecimiento estaba contabilizado en el sitio correcto. Lo que estaba mal era la
prosa que explicaba `base`, y es lo que se corrige aqui.

**Correccion 2: `per_subtask` NO escala con `max_tokens`.** Multiplicar el techo
por llamada por ocho cambio el consumo un 7% con preguntas cortas, y con
contenido que pide extension las subtareas escribieron 404/313 con techo 512 y
380/306 con techo 4096: planas. El consumo por subtarea lo fija el CONTENIDO, no
el permiso. Queda por tanto descartada la idea -que se llego a proponer durante
la calibracion- de anclar `per_subtask` a un multiplo de `max_tokens`: daria un
techo diez veces mayor que el gasto, que no protege de nada porque nada llega
ahi.

Valores fijados, sobre el peor caso medido (10113 tokens, modo `pipeline`,
`n=6`, `max_tokens` 4096) con holgura de aproximadamente 2x:

- `base: 2000`
- `per_subtask: 3000`

Comprobaciones: `pipeline` con `n=6` concede 20000 frente a 10113 medidos, y con
`n=4` concede 14000 frente a 8019. `coverage` con `n=4` concede
`2000 + 3000 * 4 * (1+2) = 38000` frente a 4776 medidos: holgado, pero es el
factor de reintentos que D2 exige contabilizar, y aun agotando los reintentos el
gasto rondaria 14000. Sobre trabajo corto (`n=8`, 6168 medidos) concede 26000.
Un techo no debe morder el trabajo sano: solo debe existir para el trabajo
desbocado.

Estos valores son de PLANTILLA y de esquema. Un despliegue que suba el
`max_tokens` de sus perfiles no necesita moverlos, porque el consumo no escala
con ese techo; lo que si debe revisar es si su contenido tipico es mucho mas
extenso que el medido aqui.

## Motivo

### Por que crecer con el plan, y no subir el techo

Subir la constante a 16384 arregla el laboratorio de hoy y vuelve a romperse en
cuanto una tarea derive el doble de unidades. El defecto no es que el numero sea
pequeno: es que un plan de 1 unidad y un plan de 12 reciben lo mismo. Un techo
constante penaliza exactamente la descomposicion, que es la razon de ser de
`task.run`. Mientras la constante exista, la capacidad castiga su propio proposito.

### Por que un presupuesto y no solo el reloj

`max_time_s` acota el gasto de forma mas directa en un backend local, y podria
argumentarse que el limite de tokens sobra. Se conserva por tres razones:

1. La bateria de conformance necesita una cota REPRODUCIBLE: un corte por tiempo
   depende de la maquina, uno por tokens no.
2. ADR 0008 hace del presupuesto un concepto de primera clase de la estabilidad
   de la entidad, no un detalle de implementacion.
3. `ia_nest_core_pulse` (ADR 0037) regula parametros tecnicos DENTRO de los
   techos del core. Sin un techo declarado y con significado, no tiene contra
   que regular; con el actual, regularia contra una cifra que miente.

### Por que la ventana por llamada se observa y no se predice

Es la unica parte de ADR 0008 que hoy no se cumple, y la tentacion es estimarla
antes de enviar. Estimar tokens exige el tokenizador del modelo concreto: es
especifico de backend (contra ADR 0003), es una aproximacion, y el backend ya
responde la verdad despues. Predecir mal para cortar antes es peor que observar
bien y continuar desde lo pendiente, que es lo que `coverage` ya hace con
`length`.

### Por que esto es core

El presupuesto se comprueba contra el estado interno del orquestador -plan,
ledger, contadores-, sin que ningun modelo juzgue a otro. Es el mismo criterio
que fijo ADR 0041 para sus tres invariantes, y el criterio de
`IA_NEST_CORE_CONTEXT.md` para decidir si algo es core o herramienta externa.

### El tamiz

- **Resiliencia**: una pasada nunca se abandona a medias, y una tarea que
  termina bien no se presenta como fallida.
- **Escalabilidad**: el presupuesto acompana a la descomposicion en vez de
  oponerse a ella.
- **Modularidad**: un solo concepto de presupuesto para los dos modos, en vez de
  dos limites con nombres y magnitudes distintas.
- **Sencillez**: dos numeros con significado operativo -lo que cuesta la
  maquinaria, lo que cuesta una unidad- y una formula de una linea. No se anaden
  perillas por iteracion ni por rol.
- **Estrategia**: deja a `pulse` un techo con significado y un coste por unidad
  que es justo la magnitud que necesita para regular.

## Consecuencia

- `CORE_CONTRACT.md`: el catalogo de cortes de `task.run` cambia
  `max_context_tokens` por `max_total_tokens`, unico para los dos modos; se
  documentan los campos aditivos y la regla D1.
- Esquema de configuracion: `orchestration.token_budget` entra;
  `orchestration.max_context_tokens` y `coverage.max_total_tokens` se retiran
  como campos ignorados. Las dos plantillas se actualizan.
- **Impacto de version: MINOR**. Serie pre-1.0: desaparece un corte tipado del
  contrato de `task.run` y se retira un campo del esquema de config. Los campos
  nuevos son aditivos. El numero lo corta el usuario en la reconciliacion
  (`meta POLITICA_SEMVER.md`, ADR 0030).
- **Digest de conformance: cambia**, y no solo por el nombre del corte: el caso
  que hoy espera `max_context_tokens` sobre un evaluador que dijo `done` pasa a
  esperar `task_done`. Es un cambio de expectativa DELIBERADO y se declara como
  tal; el test vigente congela el comportamiento equivocado.
- Bateria ANTES de implementar, como en v0.1, v0.2 y v0.3:
  1. plan de 1 unidad con respuestas modestas: `task_done`, presupuesto no
     vinculante (no regresion);
  2. plan de 8 unidades: la concesion crece y la tarea NO se corta donde el techo
     fijo la cortaba;
  3. evaluador `done` con gasto por encima del presupuesto: `task_done` y codigo
     de salida 0 (el caso que hoy falla);
  4. presupuesto agotado con evaluador `rerun`: corte `max_total_tokens` bajo I3
     -respuesta no vacia, codigo distinto de cero, corte explicado-;
  5. el fan-out sobrepasa su concesion a mitad de pasada: la pasada termina
     entera y el corte se decide en el limite;
  6. `coverage`: presupuesto derivado de las unidades y de
     `max_retries_per_unit`; una tarea de muchas unidades que moria en 16384
     sobrevive, y una desbocada corta en `max_total_tokens`;
  7. re-derivacion de I1/I2: gasta de la concesion en curso, no concede;
  8. compatibilidad: una config con `orchestration.max_context_tokens` y
     `coverage.max_total_tokens` valida e ignora ambos;
  9. `plan_ready`, `params` y traza exponen los campos nuevos.
- Paridad CLI/REST/MCP para los campos nuevos y para el corte renombrado
  (ADR 0036).
- Orden de implementacion previsto: una ficha para `pipeline` y otra para
  `coverage`, en ese orden; la calibracion de defaults es puerta de laboratorio
  entre ambas.
- No toca `reasoning.run` ni el `max_context_tokens` de `profiles` (ADR 0008
  intacto donde si se cumple). No toca `coverage_complete` ni
  `requirements_covered` (ADR 0038, 0041). No toca la exactitud factual
  (ADR 0025).

## Puntos reconciliados (2026-08-10)

Nota de forma, para que el registro sea auditable: en la reconciliacion el
usuario acepto D1 a D4. La version que leyo tenia solo tres bloques numerados;
los dos ultimos bloques normativos -campos nuevos y valores por defecto- iban
sin etiqueta y por eso no eran citables. Se numeran ahora como D4 y D5, sin
cambiar una linea de su contenido: el texto que el usuario aprobo es el mismo, y
su "D4 conforme" queda anclado a los campos aditivos.

Los dos puntos que se dejaron abiertos quedan resueltos por el usuario:

**P1. Unificar `coverage` en el mismo presupuesto. RECONCILIADO: se unifica.**
Se adopta la recomendacion. `coverage.max_total_tokens` se retira y el modo
`coverage` pasa al presupuesto de D2; el corte tipado es `max_total_tokens` para
los dos modos, como fija D3. Se descarta la alternativa de tocar solo
`pipeline`, mas barata en digest, porque dejaba vivas dos semanticas para el
mismo concepto -que es exactamente la entropia que esta decision viene a
cerrar-.

**P2. Parche puente. RECONCILIADO: se hace.**
Ficha de correccion propia, impacto PATCH, sin tocar contrato, ANTES de la linea
MINOR: subir el default de `max_context_tokens` y corregir la precedencia del
merito sobre el techo, para que `task.run` sea usable en el laboratorio sin
esperar a que entre esta decision. No sustituye a este ADR -no arregla el
crecimiento- y su unico coste es que el numero se retira despues, cuando D2
entre. La correccion de precedencia se justifica por si sola: es un fallo
observable, y el test vigente congela la expectativa equivocada.

## Alternativas descartadas

- **Subir el techo constante y no tocar nada mas.** Una linea, sin impacto de
  contrato, arregla el sintoma de hoy. Descartada como DECISION porque conserva
  el defecto estructural -el plan de 12 unidades y el de 1 reciben lo mismo- y
  garantiza volver a esta conversacion. Sobrevive como parche puente (P2), que es
  otra cosa.
- **Retirar por completo el limite de tokens y confiar en `max_time_s`,
  `max_subtasks` y `max_iterations`.** Es la opcion mas simple y la mas fiel al
  principio anti-entropia: tres limites ya acotan la tarea y el de tokens solo ha
  producido cortes espurios. Descartada por las tres razones del motivo:
  reproducibilidad de la bateria, ADR 0008, y el techo que `pulse` necesita para
  regular.
- **Derivar el presupuesto de los perfiles** (`max_tokens` x llamadas
  previstas), sin ninguna perilla nueva: imposible de contradecir por
  construccion y config cero. Descartada porque el perfil aplicable solo se
  conoce DESPUES de enrutar cada subtarea, y en un roster multi-modelo pueden ser
  varios; ademas deja el techo implicito e invisible, sin palanca para el
  operador.
- **Estimar tokens antes de enviar para proteger la ventana por llamada.**
  Descartada: especifica de backend (ADR 0003), aproximada, y redundante con
  `finish_reason=length`, que ya dice la verdad.
- **Un presupuesto por rol** (planificador, subtarea, combinador, evaluador).
  Mas fino y mas justo en teoria. Descartada por anti-entropia: cuatro perillas
  donde dos bastan, sin ningun caso que pida repartir a ese detalle.
- **Presupuesto por iteracion en vez de por tarea** (`max_tokens_per_iteration`).
  Simple y acotado, pero deja el total de la tarea sin cota y convierte
  `max_iterations` en el unico freno real del gasto.
- **Conservar el nombre `max_context_tokens` para el nuevo presupuesto**, para no
  cambiar el catalogo de cortes y ahorrar el MINOR. Descartada: perpetuar el
  nombre equivocado es lo que permitio que la semantica entrase por inferencia.
  El coste de renombrar se paga una vez.
