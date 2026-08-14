# Decision 0048: la respuesta de task.plan es la peticion de task.run (enmienda de ADR 0047)

Fecha: 2026-08-14
Estado: reconciliado por el usuario (2026-08-14), sin puntos abiertos
Enmienda a: ADR 0047 (D1 y D3), que a su vez enmienda ADR 0040
Depende de: ADR 0045 (niveles de esfuerzo), ADR 0041 (requisitos y degradaciones)

## Contexto

ADR 0047 dejo el plan como un objeto que TRANSPORTA la contabilidad del core:
dentro viajaban el `effort` con el que se derivo y los `requirements` extraidos.
La capa de encima recibe ese objeto, enriquece los prompts de sus subtareas y lo
devuelve.

Nada de eso estaba implementado todavia, y al preparar la bateria aparecio la
pregunta incomoda: si la capa devolvera el plan integro o solo los prompts. Se
fue a buscar la respuesta al codigo de `ia_nest_extended`, y lo que se encontro
no fue una respuesta sino un modo de fallo:

- Su reenvio generico es OPACO (`clients.py`, `forward`): mete un diccionario y
  devuelve lo que el core conteste, sin modelar nada. Ahi el plan viajaria
  intacto.
- Pero `task.run` es una capacidad que esa capa SOBREESCRIBE, y su regla
  declarada es "tipado donde se sobreescribe, opaco donde se reenvia". Un cliente
  que modela el plan con un tipo propio para manipularlo **descarta al
  re-serializar los campos que no modela**. No por descuido: por construccion.
- Su enriquecimiento es una transformacion de prompt y nada mas
  (`EnrichResult.enriched_prompt`, envoltorio `<enrichment_context>`), asi que lo
  unico que esa capa tiene motivo para modelar son los prompts.

Es decir: la primera implementacion honesta que alguien escriba pierde
`requirements` y `effort`, y la tarea entra por la via degradada sin que nadie lo
haya decidido.

El problema no es la capa. Es que el core metio datos SUYOS dentro de una
estructura que otro edita, y con eso hizo depender su correccion de la fidelidad
ajena. Pedir por documentacion que "el plan se trate como opaco" seria poner una
regla de comportamiento donde falta una forma que no admita el error: la clase de
costura que ADR 0035 enseño a no construir.

## Decision

**La respuesta de `task.plan` es la peticion de `task.run`.** Los datos del core
y los datos de la capa viajan como campos HERMANOS, al mismo nivel, no anidados
unos dentro de otros.

`task.plan` devuelve:

- `plan`: las subtareas (`index`, `prompt`, `domain`, `depends_on`),
- `requirements`: los requisitos extraidos (`id`, `statement` y `covered_by`;
  ver la regla de abajo),
- `effort`: el nivel resuelto con el que se derivo,
- `params` y trazabilidad, informativos como en el resto de capacidades.

`task.run` acepta, ademas del `prompt` original:

- `plan`, `requirements` y `effort`, los mismos tres campos.

La capa edita los `prompt` de `plan[]` -lo unico que es suyo- y copia los otros
dos campos tal cual. No tiene que respetar nada que este dentro de una estructura
que manipula, porque ya no hay nada dentro.

### La regla que ordena que va donde: nada de perdida silenciosa en `plan[]`

Al congelar la bateria aparecio el caso limite: la comprobacion de cobertura se
apoya hoy en un campo `covers` por subtarea -que subtareas cubren que requisitos-
y ese campo viaja YA dentro de cada elemento de `plan[]` en el checkpoint
`plan_ready`, sin estar documentado en el contrato.

`covers` es contabilidad del core dentro de la estructura que la capa edita: la
misma enfermedad que esta decision cura, un nivel mas abajo. Se corrige
invirtiendo la relacion. Cada requisito declara que subtareas lo cubren:

    requirements: [ {"id": "r1", "statement": "...", "covered_by": [0, 2]} ]

Y `plan[]` se queda con `index`, `prompt`, `domain` y `depends_on`.

La regla general, que es lo que hay que recordar cuando se anada algo:

> Dentro de `plan[]` no vive ningun campo cuya perdida sea SILENCIOSA. Todo lo
> que hay ahi es estructuralmente necesario para ejecutar -si la capa lo tira, el
> plan es invalido y falla ruidosamente con `PlanParseError` o
> `PlanDependencyError`-. La contabilidad, cuya perdida solo degrada, vive en
> `requirements`, que la capa copia entero sin modelarlo.

Consecuencias:

- El checkpoint `plan_ready` emite los requisitos con `covered_by` y el plan sin
  `covers`, en las DOS vias (plan derivado y plan suministrado): una sola forma,
  no una por procedencia.
- El formato que el core pide a su planificador NO cambia: se le sigue pidiendo
  `covers` por subtarea, y el core invierte al construir la salida publica. Es
  una transformacion de tres lineas y evita re-afinar el prompt del
  planificador.
- Cambia la forma de un evento publico: el digest de conformidad se movera al
  integrar la bateria en la fase B3, declarado por adelantado.

### Reglas de omision, todas visibles

- Sin `plan`, `task.run` se comporta exactamente como sin esta entrada. Opt-in,
  cero regresion (ADR 0040 intacto).
- Sin `effort`, se aplica la precedencia de SIEMPRE (ADR 0045): lo explicito, y
  si no, `orchestration.default_effort`. **La regla de herencia desde el plan que
  fijaba ADR 0047 D1 DESAPARECE**, porque ya no hay effort dentro del plan. Es
  una regla menos, no una mas: el esfuerzo se comporta igual con plan y sin plan,
  y el nivel realmente usado viaja en `params.effort` de la respuesta.
- Sin `requirements`, el core no los reinventa -eso seria llamar al planificador
  que esta entrada viene a evitar- y declara la degradacion
  `{stage: plan, reason: requirements_unavailable, action: skip_coverage_check}`
  con `requirements_covered=false` (ADR 0047 D3, sin cambios).
- `plan_attempts` vale 0 con `plan_source=supplied`, y el presupuesto se concede
  como a cualquier plan (ADR 0047 D2 y D4, sin cambios).

### Consecuencia sobre la pregunta abierta

Deja de haber pregunta: no hay un plan integro que devolver o no devolver. Hay
tres campos, y omitir uno es un acto explicito con consecuencia declarada en la
respuesta. Lo que quedaba pendiente de `ia_nest_extended` pasa de pregunta a nota
informativa.

## Alternativas descartadas

- **Recomendar por documentacion que el plan se trate como opaco.** Es una regla
  de comportamiento donde hace falta una forma. Funciona hasta el primer
  implementador que no lea el brief, y falla en silencio.
- **`plan_id` con estado en el core**: `task.plan` devuelve un identificador y el
  core recuerda el resto. Es la que mejor suena y la peor que hay: obliga al core
  a guardar estado entre dos llamadas, con caducidad y desalojo, y se rompe en
  cuanto haya dos instancias detras de un balanceador. Cambia un problema de
  fidelidad por uno de infraestructura.
- **Digest firmado o token opaco que la capa debe devolver.** Contrato permanente
  para vigilar un fallo que todavia no ha ocurrido, y que ademas se pierde
  exactamente igual que los campos que viene a proteger si el cliente modela la
  peticion. Leccion de ADR 0035.
- **Que el core re-extraiga los requisitos cuando no vienen.** Gasta la llamada
  al planificador que la entrada `plan` existe para evitar, y produciria
  requisitos que nadie garantiza que correspondan al plan enriquecido.

## Coste, dicho sin adornos

- Tres campos en la peticion en vez de uno. Una capa perezosa puede mandar solo
  `plan` y quedarse en la via degradada; la diferencia es que ahora eso se ve en
  el cuerpo de su peticion, no en un serializador.
- La simetria no es literal: `params` de la respuesta es informativo y no se
  devuelve. Se acepta porque `params` es un informe, no una entrada, y eso vale
  para todas las capacidades del core.

## Consecuencia

- `CORE_CONTRACT.md`: `task.plan` y la entrada `plan` con esta forma.
- Bateria (fase v0.4-B2): al plan suministrado se le anaden los casos de omision
  -sin `requirements` -> degradacion declarada; sin `effort` -> default con su
  cifra visible en `params.effort`- y desaparece el caso de herencia de esfuerzo
  desde el plan, que esta decision retira.
- Fase v0.4-B3: gate de laboratorio con el consumidor real, comprobando que
  `degradations` viene vacio y que `params.effort` es el que planifico. La
  capacidad se cierra cuando alguien la ejerce, no cuando compila (ADR 0035).
- Impacto de version: adicion compatible (PATCH por politica), publicada dentro
  de v0.4.0. Nada de esto estaba implementado, asi que mover la forma ahora no
  cuesta migracion a nadie.
