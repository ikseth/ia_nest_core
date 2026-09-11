# Decision 0052: la respuesta del core se describe a si misma

Fecha: 2026-09-11
Estado: reconciliado por el usuario (2026-09-11)

Depende de: ADR 0046 (catalogo unico de capacidades), ADR 0015 (esquema de
traza), ADR 0030 y `docs/VERSIONADO.md` (que cuenta como contrato publico),
ADR 0032 (dependencias entre capas), meta ADR 0007 (arquitectura de capas).

Dispone tres Change Requests de `ia_nest_extended`, los tres verificados por el
cable contra `v0.4.0` antes de decidir: `extended CR-0003` (identificador de
build), `extended CR-0004` (presentacion en el catalogo) y `extended CR-0005`
(trace en `prompt.stream`).

## Contexto: tres quejas, un solo punto ciego

Los tres CR llegaron por separado, con tres semanas de diferencia entre el
primero y esta disposicion, y parecian tres cosas distintas. Al medirlos
resultaron ser sintomas del mismo hueco.

**El contrato del core describe con detalle lo que se le ENVIA y lo que su motor
HACE, y casi nada sobre la respuesta como objeto.** Medido en el catalogo de
`v0.4.0`, una capacidad publica esto:

    cli: action, aliases, description, epilog, flag_help, flags, group, inputs, order
    params: name, type, required, default, choices, metavar, summary
    mcp: tool          rest: method, path          streaming: true|false

Todo eso describe COMO SE LLAMA. De lo que vuelve, el catalogo dice una sola
cosa: si es streaming o no.

Las consecuencias, las tres medidas:

1. Dos procesos que sirven artefactos distintos de la misma version responden lo
   mismo. `core_version` sale del manifiesto del paquete, no del artefacto
   cargado. Le costo tres horas de medidas invalidas a extended, y antes al
   propio core, que declaro un smoke "sobre main exacto" que por REST no lo fue.
2. De las tres capacidades de streaming, dos publican `trace` con `request_id` y
   una no:

        prompt.stream     -> {finish_reason, model, reasoning, text, tokens_*}
        reasoning.stream  -> {..., trace: {request_id, capability, status, ...}}
        task.stream       -> {..., trace: {request_id, capability, ...}}

   `prompt.stream` es la rara de tres, y ademas tampoco publica `domain`.
3. Quien reenvia una capacidad no puede presentarla como la presenta el core,
   porque los renderizadores viven en un diccionario de su CLI. El operador que
   sube de capa recibe MENOS que abajo, que es lo que meta ADR 0007 prohibe.

El punto ciego explica por que el gate de ADR 0046 -que existe para que las
interfaces no deriven, y que destapo `tags` sin que nadie lo tocara- no pudo ver
el caso 2: **ese gate compara superficies de ENTRADA.** Nada vigila la salida.

## Decision

El catalogo y la respuesta del core describen tres cosas sobre si mismos: QUE
ARTEFACTO los produjo, QUE REQUEST los produjo, y COMO SE LEEN. Ninguna de las
tres es logica de motor, y por eso ninguna estaba; las tres son necesarias para
que otra capa pueda auditar y presentar lo que reenvia.

### D1. Identidad del artefacto servido (`extended CR-0003`, REFORMULADO)

`runtime.health` y `capability.list` publican `build_id`, hermano de
`core_version`.

**Se acepta la necesidad y se cambia la forma que el CR sugeria.** El CR pedia
"el identificador del commit desplegado". Esa forma no responde a su propio caso
de uso: un identificador leido de git describe el ARBOL DE TRABAJO, y el arbol de
trabajo es exactamente lo que mintio -decia `v0.4.0` mientras el proceso servia
codigo de veintiun commits antes-. Un consumidor que preguntara por el commit
habria recibido la misma respuesta tranquilizadora.

`build_id` es, por tanto, un digest del PAQUETE CARGADO, calculado sobre los
ficheros del modulo que el proceso importo:

- no depende de git, asi que vale instalado desde un wheel o en editable;
- dos builds de la misma version dan digests distintos, que es la pregunta del
  CR;
- el mismo build en dos maquinas da el mismo digest, que es lo que permite a un
  consumidor afirmar contra que midio;
- si no se puede calcular, vale `unknown` explicito, coherente con como
  `runtime.health` ya trata lo que no puede sondear.

Regla normativa, que el propio CR pide preservar y aqui se hace contrato:
**`core_version` gobierna el vinculo por SemVer; `build_id` es observabilidad y
NO se usa para fijar dependencias.** Son dos ejes y ninguno sustituye al otro.

Lo que se pierde y se asume: un digest no le dice a un humano QUE version del
codigo es. Para eso esta el repo. El campo sirve para responder si dos cosas son
la misma, que es lo unico que un consumidor remoto no puede averiguar por su
cuenta.

### D2. Trace simetrico en las capacidades hermanas (`extended CR-0005`, ACEPTADO)

`prompt.stream` publica en su evento `done` el mismo objeto `trace` que ya
publican `reasoning.stream` y `task.stream`.

No es capacidad nueva: es una DERIVA. La regla de compatibilidad del propio core
dice que sus interfaces no deben divergir, y aqui divergen dos capacidades
hermanas del mismo tipo. Que la mas barata de las tres sea la que no se puede
auditar no es una simplificacion deliberada; nadie la decidio.

Alcance: el evento `done`. No cambian los eventos de token, ni el formato del
flujo, ni nada de `task.stream`.

### D3. El catalogo declara como se lee una respuesta (`extended CR-0004`, ACEPTADO en forma gruesa)

Cada capacidad declara en su proyeccion de CLI un descriptor de PRESENTACION de
su respuesta. El core declara QUE SE LEE; nunca COMO SE PINTA.

El argumento con el que este CR se iba a rechazar -"la presentacion no es asunto
del core"- **no se sostiene, y lo tumba el propio catalogo**: `description`,
`epilog`, `metavar`, `flag_help` y `order` son presentacion pura, publicada desde
ADR 0046. El core ya publica su piel; lo que hace es publicar solo la mitad de
entrada y llamar privada a la de salida. Esa asimetria es el defecto.

Formas declarables, sacadas de lo que los renderizadores HACEN hoy, no de lo que
seria bonito soportar:

- `text`: se imprime un campo tal cual (`prompt.run` -> `response`,
  `reasoning.run` -> `output`);
- `row`: una fila con varios campos (`domain.route` -> `domain`, `model`,
  `reason`);
- `table`: una fila por elemento de una lista, con sus columnas (`task.plan` ->
  `plan[]` con `index`, `domain`, `prompt`);
- `opaque`: el core no declara presentacion para esta respuesta.

`opaque` no es una escapatoria: es informacion. Medido, tres renderizadores no
caben en las otras formas -`runtime.detect` DERIVA una etiqueta de un booleano,
`model.pull` pinta dos listas con un prefijo literal, `config.validate` imprime
una constante que no esta en la respuesta-. Declararlos opacos le dice a quien
reenvia "aqui cae a JSON a proposito", que es distinto de no saberlo. El propio
CR lo pide con esas palabras.

Fuera de alcance, explicitamente: la presentacion del PROGRESO de las capacidades
de streaming. Eso es una vista en vivo de eventos que el consumidor ya modela, no
la presentacion de una respuesta.

### D4. El gate de ADR 0046 se extiende a la salida

Lo anterior se desincroniza en cuanto alguien edite un renderizador, que es
exactamente la historia de `tags`. Asi que el gate bidireccional del catalogo
pasa a cubrir tambien la salida: toda capacidad con proyeccion de CLI declara
presentacion, y lo declarado coincide con lo que su renderizador hace.

Sin esta decision, D3 nace siendo documentacion que envejece. Con ella, el
catalogo vuelve a ser lo que ADR 0046 quiso: fuente unica, no copia.

## Lo que NO se decide aqui

- Un motor de plantillas, anchos, colores, i18n o cualquier estilo. El core
  declara campos, no aspecto.
- Publicar el commit, la rama o la topologia del despliegue. `build_id` no es
  legible ni pretende serlo.
- Tocar `task.stream` o el formato de los flujos.

## Impacto de version

PATCH. Las tres decisiones son adiciones: dos campos nuevos (`build_id`,
`presentation`), un campo que aparece en un evento donde no estaba (`trace` en el
`done` de `prompt.stream`), y ningun renombrado, ninguna retirada y ningun cambio
de significado. El numero lo corta el usuario.

Aviso a quien consuma: `capability.list` y `runtime.health` crecen en claves.
La regla de compatibilidad del core ya obliga a tolerar lo que no se conoce.
