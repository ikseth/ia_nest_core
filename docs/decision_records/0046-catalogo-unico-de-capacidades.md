# Decision 0046: catalogo unico de capacidades, del que se derivan las interfaces

Fecha: 2026-08-14
Estado: reconciliado por el usuario (2026-08-14), sin puntos abiertos
Origen: `extended CR-0002` (descubrimiento de capacidades en REST)
Depende de: ADR 0009 (adoptar antes que construir), ADR 0021 (REST Starlette),
ADR 0006 (version de protocolo MCP)

## Contexto

### Lo que pide la capa de abajo

`ia_nest_extended` construye su interfaz de consumo sobre el contrato uniforme
del ente (`meta ADR 0007`): una capa reexpone el contrato completo de la que
envuelve y reenvia de forma generica lo que no transforma, de modo que una
capacidad nueva del core sea alcanzable desde arriba sin editar nada.

Verificado contra el codigo, eso se cumple en REST (rutas proxeables) y en MCP
(herramientas enumerables por el protocolo), pero no en CLI: un CLI necesita
ENUMERAR sus subcomandos para construir su ayuda, y sin catalogo consultable
solo puede llevar una lista escrita a mano que se desactualiza en silencio.

### Lo que el core encuentra al mirarse

La peticion es legitima, pero el motivo que obliga es interno. El core tiene una
regla de compatibilidad propia -"MCP y REST no deben tener logica distinta a la
CLI" (`CORE_CONTRACT.md`)- que hoy no comprueba nadie, y la superficie ya derivo:

| capacidad | CLI | REST | MCP |
|---|---|---|---|
| `prompt.run`, `reasoning.run`, `domain.route`, `model.list`, `domain.list`, `config.validate`, `eval.run`, `runtime.health` | si | si | si |
| `prompt.stream`, `reasoning.stream` | si | si | NO |
| `task.run` | si | solo SSE | solo bloqueante |
| `model.pull` (provisioning, ADR 0029: contrato publico) | si | NO | NO |
| `init` (bootstrap, ADR 0027) | si | NO | NO |

La LOGICA si es unica: las tres interfaces llaman a `service.py`. Lo que esta
triplicado es el CATALOGO. El hecho "existe `prompt.run`, va por
`POST /prompt/run`, lleva identidad, no es streaming" esta escrito en el parser
de `cli.py`, en la tabla de rutas de `rest.py` y en el decorador
`@server.tool(name=...)` de `mcp_server.py`. Nada obliga a que los tres digan lo
mismo, y ya no lo dicen.

Anadir `capability.list` como CUARTO sitio donde repetir el mismo dato seria
agravar la causa mientras se atiende el sintoma. El CR lo senala y acierta.

## Decision

### D1: existe un catalogo declarativo unico

Un modulo del core (`capabilities.py`) declara, sin logica, una entrada por
capacidad publica. Es la FUENTE de la verdad sobre que capacidades hay y como se
invocan. Campos de cada entrada:

- `name`: identificador canonico (`prompt.run`), el mismo en las tres
  interfaces.
- `summary`: descripcion corta, en el idioma de la ayuda.
- `identity`: si transporta contexto de identidad del request
  (`CORE_CONTRACT.md`).
- `streaming`: si su respuesta es un flujo de eventos.
- `params`: lista de parametros (`name`, `type`, `required`, `choices`,
  `default`, `summary`).
- `rest`: `{path, method}` o nulo si no se expone por REST.
- `cli`: `{group, action, aliases}` o nulo.
- `mcp`: `{tool}` o nulo.

Los parametros ya son contrato publico hoy (una bandera CLI nueva o un campo de
cuerpo REST nuevo son adicion compatible segun `docs/VERSIONADO.md`). El
catalogo no los convierte en contrato: los hace legibles por maquina.

### D2: dos interfaces se DERIVAN, una se ASERTA

- **REST**: la tabla de rutas se construye recorriendo el catalogo. El handler
  sigue escrito -es donde se extrae el cuerpo-, pero ruta, metodo y forma salen
  del catalogo.
- **CLI**: el parser de `argparse` se construye recorriendo el catalogo. Los
  textos de ayuda, epilogos y `choices` viven en el catalogo como DATOS: la
  ergonomia escrita a mano no se pierde, cambia de sitio.
- **MCP**: las funciones tipadas se conservan escritas y un test de conformidad
  aserta, campo a campo, que su nombre y su firma coinciden con el catalogo.

La excepcion de MCP no es preferencia: el SDK deriva el esquema de cada
herramienta de la FIRMA de la funcion (`@server.tool` sobre una funcion con
anotaciones). Generarlas obligaria a sintetizar firmas en tiempo de ejecucion,
que es metaprogramacion para ahorrar nueve declaraciones. La asercion da la
misma garantia -divergir rompe el build- sin construir un generador de
funciones.

### D3: `capability.list` es capacidad publica en las TRES interfaces

El CR pide REST. El core dispone paridad, porque exponerla solo en REST crearia
exactamente la asimetria que esta decision viene a cerrar:
`ianest capability list`, `GET /capability/list` y herramienta MCP
`capability.list`. No requiere identidad (es introspeccion, como `model.list`).

Devuelve el catalogo completo, incluida su propia entrada -quien proxea tiene
que saber que puede reenviarla- y las capacidades que no se exponen en alguna
interfaz, con `null` en la proyeccion que falta. Declarar los huecos es parte de
decir la verdad: un consumidor que ve `rest: null` sabe que eso no se proxea, en
vez de descubrirlo con un 404.

### D4: el core declara su version

`capability.list` devuelve `core_version`, y `runtime.health` gana el mismo
campo. Hoy `runtime.health` informa de python, plataforma, GPU y version de
protocolo MCP, pero no de la version del propio core: la unica cifra con la que
el ente vincula capas (`meta REGISTRO_CAPAS.md`, ADR 0032) no era consultable en
ejecucion. Una capa que fija `core >=0.2 <0.4` no podia verificar contra que
esta hablando.

### D5: la deriva se declara; solo se cierra un hueco

El catalogo obliga a que cada hueco sea una decision escrita. Se resuelven asi:

- **`model.pull` queda solo en CLI, por decision.** Es operacion de operador, no
  capacidad del ente (`meta ARQUITECTURA_DE_CAPAS.md`, seccion 5), y abrirla por
  red seria permitir que un tercero dispare descargas de gigabytes en la maquina
  del core. `init` queda solo en CLI por el mismo motivo, agravado: escribe en el
  sistema de ficheros local.
- **`prompt.stream` y `reasoning.stream` quedan sin MCP, por forma del
  protocolo.** Una herramienta MCP devuelve un resultado; el equivalente al
  streaming es la variante bloqueante, que ya existe.
- **`task.run` gana su variante bloqueante en REST.** Es el unico hueco real de
  los tres: MCP si tiene esa variante y REST no, con lo que un cliente REST que
  solo quiere el resultado esta obligado a hablar SSE para nada. La forma se fija
  en la enmienda de abajo.

### Enmienda D5-a: task.run pasa a JSON y nace task.stream (2026-08-14)

Reconciliada el mismo dia que el ADR, al fijar las rutas para congelar la
bateria. La redaccion original decia que `POST /task/run` seguiria siendo SSE y
que el camino bloqueante se anadiria aparte. Se cambia, y este es el motivo:

`ia_nest_extended` no lleva tabla de rutas. Su cliente DERIVA la ruta del nombre
de la capacidad -`prompt.run` -> `/prompt/run`, sustituyendo puntos por barras-
para que una capacidad nueva del core le sea alcanzable sin tocar codigo
(`clients.py`, `capability_route`). Es exactamente el mecanismo generico que
`meta ADR 0007` persigue, y convierte el NOMBRE de la capacidad en contrato.

Con `task.run` devolviendo SSE, el sufijo `.run` significaria JSON en dos
familias y flujo en la tercera, y quien reenvia de forma generica tendria que
saberlo de memoria: justo el conocimiento por capacidad que el catalogo viene a
eliminar. Anadir el bloqueante con un nombre fuera de patron (`task.complete`,
`task.result`) traslada el problema al nombre.

Forma adoptada, alineada con `prompt` y `reasoning`:

- `task.run` -> `POST /task/run`, JSON con el resultado final.
- `task.stream` -> `POST /task/stream`, SSE, que es lo que hoy hace `/task/run`.

`X.run` es siempre bloqueante y `X.stream` siempre flujo, en las tres familias.
La bandera `streaming` del catalogo deja de ser informativa y pasa a ser
operativa: un reenviador generico la consulta en vez de llevar la lista a mano.

Coste, dicho sin adornos: **rompe** a quien hoy haga POST a `/task/run`
esperando eventos, y ese alguien es `ia_nest_extended`, que declara `task.run`
entre las capacidades que sobreescribe. Se asume porque su pin (`core >=0.2
<0.4`) impide que v0.4.0 le entre sola, porque el aviso esta dado por el canal
de CR antes de que suba el pin, y porque la alternativa era conservar para
siempre una asimetria en el contrato que este ADR existe para eliminar.

Impacto de esta pieza: rompe contrato REST -> MINOR, coherente con la linea.

## Motivo de la forma elegida

### Por que un catalogo y no simplemente una capacidad mas

Porque el problema no era que faltase una lista: era que la lista existia por
triplicado y sin arbitro. Anadir `capability.list` sobre una cuarta copia
resolveria el caso de uso de extended y dejaria el core con mas deuda de la que
tenia. La regla de compatibilidad del `CORE_CONTRACT.md` pasa de promesa escrita
a gate automatico: si manana alguien anade una capacidad a REST y se olvida de
la CLI, el test falla.

### Por que derivar y no solo asertar

La primera version de esta decision proponia asertar las tres interfaces,
conservando la CLI escrita a mano por su ergonomia. Se descarta tras la
reconciliacion: el codigo duplicado, aunque este vigilado, sigue siendo codigo
duplicado, y la ayuda de la CLI es DATO -texto, `choices`, obligatoriedad-, no
logica. Cabe en el catalogo sin perder calidad, y lo que no cabe (la firma
tipada que MCP necesita) es exactamente donde se aserta.

### Lo que esto cuesta

- El catalogo acaba modelando parametros: un pequeno vocabulario declarativo
  interno. Es el precio de generar dos interfaces, y se paga una vez.
- `cli.py` se reescribe en su parte de construccion del parser. Es refactor
  interno: la superficie observable no cambia, y los tests de ayuda existentes
  son la red.
- Cada capacidad nueva se declara en el catalogo y, si va por MCP, tambien como
  funcion tipada. Dos sitios en vez de tres, con el segundo verificado.

## Alternativas descartadas

- **`capability.list` como cuarta copia del catalogo.** Resuelve el CR y agrava
  la causa. Es el anti-patron que el propio CR senala.
- **Asertar las tres interfaces sin generar ninguna.** Menos trabajo y misma
  garantia contra la deriva, pero conserva la duplicacion. Descartada en
  reconciliacion: el criterio del usuario es que el codigo duplicado no se
  vigila, se elimina.
- **Generar tambien MCP.** Exige sintetizar firmas en ejecucion para que el SDK
  derive su esquema. Metaprogramacion sin retorno proporcionado.
- **Exponer `capability.list` solo en REST, como pedia el CR.** Crearia la
  asimetria que la decision cierra.
- **No ofrecer descubrimiento y que cada capa lleve su lista estatica.** Es el
  dato del core replicado a mano en cada capa superior; se desactualiza en
  silencio y contradice el hogar unico (`meta ADR 0008`).
- **Descubrir por MCP desde extended.** Funciona hoy sin tocar el core, pero
  obliga a meter un cliente MCP en el CLI de la capa solo para pintar su ayuda.

## Consecuencia

- `CORE_CONTRACT.md`: `capability.list` como capacidad publica; `core_version`
  en `runtime.health`; variante bloqueante de `task.run` por REST.
- `docs/PLAN.md`: tramo A de la linea v0.4.
- Impacto de version: adicion compatible. Por `meta POLITICA_SEMVER.md` seccion
  3 (serie pre-1.0) eso es PATCH; se publica dentro de la linea v0.4.0, que el
  usuario corta como MINOR por envergadura (precedente ADR 0034 y ADR 0038).
- `extended CR-0002` pasa a `aceptado` en `ia_nest_meta`, con respuesta por
  handoff y tres preguntas de vuelta: si su CLI deriva el subcomando del nombre
  o necesita la proyeccion explicita, si consumira el esquema de parametros
  ahora que existira, y si el plan de `task.plan` viajara integro de vuelta
  (ADR 0047).
- No reabre `core ADR 0031`, `0035` ni `0040`, ni invierte el grafo de
  dependencias: el core no aprende nada de las capas de arriba, solo sabe decir
  lo que el mismo hace.
