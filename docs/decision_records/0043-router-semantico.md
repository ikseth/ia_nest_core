# Decision 0043: el router de dominios es un clasificador semantico, no un filtro de palabras clave

Fecha: 2026-08-07
Estado: reconciliado por el usuario (2026-08-07)

## Contexto: lo que hay hoy, y por que no es lo acordado

El contrato de `domain.route` (`CORE_CONTRACT.md`) promete devolver "dominio
seleccionado, confianza, motivo breve, alternativas relevantes". Eso es el
lenguaje de un CLASIFICADOR: la confianza y el motivo solo tienen sentido si un
juicio los produce.

La implementacion, en cambio, es un filtro lexico: `DomainRouter._matches`
busca substrings de `routing_rules.keywords` en el prompt en minusculas, y
`confidence = 1.0 if matches else 0.0` (`domain_router.py`). La confianza esta
FALSEADA: un match de keyword no la tiene, se pone 1.0 a pelo. Ningun ADR
decidio el enrutado por keywords; entro como "reglas declarativas" en la fase
6b, apoyado en el esquema de config (ADR 0014). Fue un andamio de arranque.

Evidencia de laboratorio (2026-08-07): un texto filosofico enruto a
`razonamiento` porque contenia la palabra "logica", y de ahi a un modelo
inadecuado para la tarea. El filtro reparte por presencia de palabras, no por
sentido.

## Decision

El enrutado por dominio del core pasa a ser SEMANTICO: un modelo clasifica el
prompt por su sentido contra el catalogo de dominios y elige, con confianza y
motivo reales. El filtro de palabras clave se retira.

### Un solo router, para domain.route y task.run

Hay UNA pieza de enrutado semantico, el clasificador que respalda la capacidad
`domain.route` (que se conserva publica). Tiene dos consumidores:

- La propia capacidad `domain.route`: un consumidor externo pide "que dominio
  elegirias para esto" sin ejecutar. Ahora responde por sentido, con confianza
  y motivo reales.
- `task.run`: la resolucion de dominio de cada subtarea pasa por ese mismo
  router. El planificador DESCOMPONE; no enruta. Su antiguo `domain_hint` deja
  de ser un match de cadena y pasa a ser, como mucho, contexto asesor que el
  router recibe junto al prompt de la subtarea y al objetivo padre.

No conviven dos mecanismos de enrutado. La resolucion de `domain_hint` por
igualdad de cadena (`_resolve_domain_hint`) y el filtro de keywords
(`_matches`) desaparecen los dos.

### prompt.run va directo: NO invoca el router

`prompt.run` es el camino atomico y rapido (excepcion tecnica frente a
`task.run`, que es el modo orquestado). NO enruta por sentido. Su precedencia:

1. modelo directo declarado -> ese modelo;
2. dominio declarado -> su `preferred_model`;
3. nada declarado -> el dominio por defecto (`general`), SIN llamar al router.

Esto ENMIENDA el punto 3 de ADR 0019: la rama "nada declarado" de `prompt.run`
resuelve al dominio por defecto, no al router (ADR 0019 ya contemplaba "o el
dominio por defecto general"; se fija esa via). Quien quiera enrutado semantico
en una peticion atomica llama antes a `domain.route` y pasa el dominio elegido,
o usa `task.run`. Asi `prompt.run` no paga ninguna llamada de clasificacion:
sigue siendo directo.

### task.run no recibe dominio: es su filosofia

`task.run` NO tiene entrada de dominio de nivel superior, y no la tendra. Cada
subtarea se enruta por su propio sentido con el router. Forzar un dominio unico
a toda la tarea contradice la orquestacion (la gracia es que reparte por
dominios); quien quiera fijar un dominio, usa `prompt.run`, que es el camino
para eso. La precedencia INTERNA de cada subtarea no cambia de forma
(modelo/dominio que el plan fije para esa subtarea > router), solo que el
ultimo recurso pasa de keywords a router semantico.

Asi los dos modos quedan limpios: `prompt.run` lo controla el que llama (sin
orquestacion, sin router); `task.run` lo reparte el core (orquesta y enruta por
sentido, sin dominio forzado).

### El catalogo que el router lee

El router clasifica contra el catalogo de dominios CONFIGURADO usando su `id` y
su `description`. Por tanto la DESCRIPCION deja de ser decorativa y pasa a ser
la entrada del clasificador: debe ser inequivoca. `routing_rules.keywords` se
retira del esquema de config.

### El router es semantico; la bateria lo prueba con un doble

El router REAL es semantico y no-determinista, por diseno. Lo que sigue siendo
determinista es la pista de CONFORMANCE, que no es el router: es un banco de
pruebas que sustituye TODO modelo por un `ScriptedFakeAdapter` (un doble con
respuesta fija), como ya hace hoy con planner, combiner y validator.
Conformance verifica el CABLEADO -que la decision del router fluye al dominio
correcto, que la traza lo registra, que la precedencia se respeta-, no la
CALIDAD del juicio.

La calidad del enrutado -si reparte bien por sentido- se prueba en la pista
SMOKE, contra backend real, sin digest reproducible, como todo lo demas. Asi el
digest de conformance se conserva sin volver determinista al router. El router
se declara en config como un objetivo mas (modelo o dominio + perfil), al
estilo de `orchestration.planner`; en conformance ese objetivo es un fake
guionizado.

### El core es agnostico en modelos

El core NO opina sobre que modelo sirve cada dominio, ni sobre sesgo, origen o
valores. Provee el mecanismo -asignacion de modelo por dominio
(`domains[].preferred_model`, ya existente)- y respeta lo que el operador
declare. Cualquier politica sobre que modelo va en cada dominio es del operador
y vive en SU config (contexto local, meta ADR 0006), no en el core. Quien
quiera modelos de cualquier origen en cualquier dominio, puede.

### Los dominios son configurables; solo el default es arquitectura

Los dominios NO son una taxonomia fija del core. Son config del operador: quien
despliega define los que quiera -cocina, filosofia zen, lo que sea- con sus
modelos y sus descripciones. El core no conoce ni impone ningun dominio
concreto; el router reparte sobre el catalogo CONFIGURADO, sea cual sea.

Lo unico ARQUITECTURA (a fuego) es que debe existir un dominio POR DEFECTO: el
recurso ultimo cuando `prompt.run` no declara nada y el punto de caida del
router cuando ningun dominio encaja. Se propone designarlo EXPLICITAMENTE en
config (un `default_domain: <id>` de nivel superior, o una marca en el dominio),
en vez del nombre magico `general` que hoy busca `DomainRouter._default_domain`:
asi ni el nombre del default queda a fuego, solo su existencia.

La plantilla versionada trae un conjunto de dominios de EJEMPLO (general,
humanidades, matematicas, codigo, linux, razonamiento) como punto de partida,
con descripciones inequivocas para que el router semantico reparta bien. Son
ejemplos, no contrato: el operador los cambia, renombra o sustituye a voluntad.
Que exista `razonamiento`, o como se llame, es decision de config, no del core.
La calidad de las descripciones (que el router lee) es responsabilidad del
operador; la plantilla solo da un buen punto de partida.

## Motivo

- **El contrato ya pedia esto.** No es una capacidad nueva: es honrar
  `domain.route` tal como esta escrito. La confianza falseada es la prueba de
  que la pieza semantica se diseno y no se construyo.
- **Es el cimiento, no el andamio** (principio del usuario: resiliencia,
  escalabilidad, estrategia). Un filtro de palabras clave exige mantener listas,
  se rompe con sinonimos y idiomas, y empuja el problema a capas de encima
  (finetuning, conscience) para tapar lo que el enrutado deberia hacer bien. Se
  acepta la merma de rendimiento a cambio del cimiento correcto.
- **Coste acotado por la precedencia.** El router solo corre en auto-route; una
  invocacion con dominio declarado no lo toca. La latencia extra es opt-in por
  no-declaracion.

## Consecuencia

- `CORE_CONTRACT.md`: `domain.route` conserva su forma (dominio, confianza,
  motivo, alternativas); cambia que ahora son reales. Se documenta que el
  enrutado es semantico y que la confianza es la del clasificador.
- Config (ADR 0014): `routing_rules.keywords`/`tags` se retiran; `description`
  pasa a ser entrada normativa del router; nuevo objetivo `router` (modelo o
  dominio + perfil). Es cambio de esquema NO aditivo.
- Impacto de version: MINOR (rompe contrato de config: `routing_rules`
  desaparece). Serie pre-1.0. El numero lo corta el usuario; linea propia
  (v0.5 o la que el usuario asigne). Misma disciplina: contrato y bateria ANTES
  de implementar.
- Digest de conformance: cambia (el ruteo pasa a model-based con router
  guionizado). Se declara el nuevo, patron v0.2-3/v0.3-2 (ADR 0017).
- Bateria ANTES de implementar: casos de conformance con router fake guionizado
  que devuelve dominio/confianza/motivo para `domain.route`; ruteo de subtareas
  de `task.run` por el router unico; `prompt.run` sin declarar nada resuelve al
  dominio por defecto SIN invocar router; precedencia (modelo/dominio declarado
  no invoca router); y que la asignacion de modelo por dominio declarada en
  config se respeta.
- Dominio por defecto: se designa explicitamente en config (nuevo, arquitectura)
  en vez del nombre magico `general`. La taxonomia concreta de dominios NO es
  del core: es config del operador; la plantilla trae ejemplos con buenas
  descripciones.
- Relacion con `capability.route` (diferido, ADR 0038): son hermanos -uno
  clasifica dominio, el otro capacidad-. Este se construye porque tiene
  consumidor hoy (el propio core); aquel sigue diferido. Podran compartir
  maquinaria de clasificacion cuando el segundo se siembre.
- Robustez del planificador (los `depends_on`/`domain_hint` invalidos vistos en
  laboratorio, 2026-08-07): relacionada pero distinta; se trata en su propia
  ficha, no aqui.
- Alternativas descartadas:
  - **Conservar keywords como atajo rapido opcional** (fast-path si hay match
    claro): mantiene el mecanismo que se quiere retirar y su mantenimiento de
    listas; el usuario elige retirarlo del todo (2026-08-07).
  - **Router solo en `domain.route`, dejando los hints de `task.run` como
    hoy**: deja dos mecanismos de enrutado conviviendo; el usuario elige router
    unico compartido (2026-08-07).
  - **Cachear la decision del router**: es memoria (indexada por identidad);
    vive en `ia_nest_extended`, no en el core (ADR 0035). No se construye aqui.
  - **Router por embeddings/similitud en el core**: es otra forma de andamio
    (umbral que mantener) y mete dependencia nueva; se prefiere el juicio de un
    modelo, que es lo que el contrato pide.
