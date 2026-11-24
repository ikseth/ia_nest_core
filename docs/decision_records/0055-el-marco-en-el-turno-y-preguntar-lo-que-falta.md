# Decision 0055: el marco en el turno y preguntar lo que falta

Fecha: 2026-11-24
Estado: aceptado por el usuario (2026-11-24), con la opcion A para preguntar

Depende de: ADR 0054 (D1, `turn_context`), ADR 0053 (D6, politica de
herramientas), ADR 0043 (`prompt.run` no enruta), meta ADR 0007 (regla 3: sin
el campo nuevo, como antes), meta ADR 0017 (puntos 5 y 7), meta ADR 0018 (D4:
el enrutador ve lo mismo que el modelo, como pista), meta ADR 0019 (nivel de
permiso y tono, separados).

Dispone `extended CR-0006` (ia_nest_core#57), **tramo B**, y la parte del core
de meta ADR 0019. Meta `H12`, paso H12P8.

## Contexto

El core no sabe con quien habla ni desde donde. Extended compone ahora el marco
de la conversacion (extended ADR 0017): canal, persona, dispositivo, lugar,
idioma y lo que falta, ya resueltos y sin ids internos. Linea base de meta
`H12`: "va a llover?" por Open WebUI se contesta sobre un lugar inventado o se
pregunta segun la redaccion del modelo (`marco-v1`, grupos B y C); y cuando
falta un dato, preguntar o suponer lo decide el modelo con su texto.

Ademas el perfil `child` hace de nivel de permiso para cualquiera que no se
identifique. Meta ADR 0019 lo separa: el nivel es `adult` o `restricted`; el
tono es de extended.

## Decision

### D1. `turn_context.frame`

Parte nueva de `turn_context` (ADR 0054, D1), con la forma que manda extended
(extended ADR 0017, punto 5): `channel`, `person`, `device`, `place`
(cada uno con `state` y sus datos), `language`, `missing` y `stated`. Se acepta
en `prompt.run`, `prompt.stream` y, desde ahora, `domain.route`, que declara
`turn_context` en el catalogo. Es dato, no instruccion. Campos desconocidos se
ignoran; un tipo invalido en un campo conocido es error de entrada. Sin `frame`,
el core se comporta como `v0.6.0`.

### D2. Pista al enrutar

Si llega `frame`, el prompt de clasificacion del enrutador gana un bloque corto
con el canal, el lugar (estado y localidad) y lo que falta. Es pista, no regla
(meta ADR 0018, D4): el dominio lo sigue eligiendo la clasificacion.

### D3. Contexto al responder

Si llega `frame`, el modelo recibe un bloque de contexto `## marco de la
conversacion` con el canal, quien habla (nombre o desconocido), el dispositivo
(nombre, compartido), el lugar (casa, localidad, zona horaria), el idioma y lo
dicho en la conversacion (`stated`). No cambia la politica de herramientas: el
nivel de permiso y el efecto (ADR 0053 D6, ADR 0054 D4) siguen decidiendo.

### D4. Preguntar como resultado declarado

- Si `missing` contiene `place` o `person` (lo que se puede preguntar; el
  dispositivo no se pregunta), antes de responder el core clasifica con una
  llamada corta al modelo del enrutador (el mismo camino que el efecto, ADR
  0054 D3) si la respuesta depende de esa parte:
  `{"needs": "place" | "person" | null, "reason": "..."}`.
- Si depende, el turno no llama al modelo para responder: termina con
  `finish_reason: "input_required"`, la traza `input_required: {"part": ...}` y
  como respuesta la pregunta de esa parte, tomada de la configuracion
  (`frame_questions`, por idioma, con un texto por defecto). En `prompt.stream`
  la pregunta sale como contenido y el `done` lleva lo mismo; sin tipos de
  evento nuevos.
- Fallo, JSON invalido o valor desconocido: no se pregunta y el turno sigue como
  sin `frame` en esa parte. Una parte que no esta en `missing` (ya `known` o
  `stated`) nunca se pregunta.
- La pregunta es un resultado del turno, no un texto que el modelo decide
  escribir. Practica: `INPUT_REQUIRED` de A2A, `elicitation` de MCP.

### D5. Nivel de permiso: `adult` o `restricted`

`interlocutor_profile` acepta `adult` y `restricted`; `child` se acepta durante
una version como nombre antiguo de `restricted` y se normaliza. En
`tools.allow`, la clave `restricted` sustituye a `child`, que se acepta durante
una version (las dos a la vez, error de configuracion). Las herramientas
permitidas no cambian.

### D6. Traza y telemetria

`done.trace` gana `frame_used` (booleano) e `input_required` cuando se pregunta;
el evento del turno registra la latencia de la clasificacion de D4. Turnos sin
`frame`: sin campos nuevos.

## Orden de despliegue

El core se programa despues de extended (usa lo que compone) y se despliega
**antes que extended y el borde**: tiene que aceptar `restricted` antes de que
nadie lo mande.

## Impacto

- Contrato: parte nueva de `turn_context`, `turn_context` en `domain.route`,
  `finish_reason` nuevo, campos aditivos en la traza, valor nuevo del perfil con
  transicion. **MINOR (`v0.7.0`)**.
- Coste declarado: una llamada mas al modelo del enrutador solo en turnos con
  `place` o `person` en `missing`. Se mide con v1-ha y `marco-v1`.

## Lo que esta decision NO hace

- El core no conoce entidades ni sesiones: recibe el marco resuelto.
- No interpreta la respuesta a una pregunta: la guarda extended.
- No pasa el marco a `reasoning.*` ni `task.*` (no hay consumidor hoy).
- `catalog` (resumen y preseleccion) sigue en meta `H13`.

## Estado posterior

2026-11-24 (`v0.7.1`, meta H12P8, fase 2): en el laboratorio, el modelo del
enrutador no acertaba el juicio compuesto de D4. Contesto `needs: null` a "va a
llover?" y pidio el lugar en "va a llover hoy en Madrid?". La llamada corta pide
ahora dos juicios: `depends_on` y `said_in_request`. El core pregunta si la
respuesta depende de una parte de `missing` y la peticion no la dice. Se sigue
aceptando `needs`. Con mistral-nemo y su perfil, 35 de 36 en 12 frases tipicas
(antes, 33 de 36 con ejemplos y menos sin ellos). El contrato del turno no
cambia.
