# Decision 0053: tool_contracts por MCP, en prompt.* y declarado por dominio

Fecha: 2026-11-06
Estado: reconciliado por el usuario (2026-11-06), decision a decision

Depende de: ADR 0007 (denegar por defecto), ADR 0022 (tool_contracts diferido
hasta una herramienta concreta), ADR 0031 (enriquecimiento no es herramienta),
ADR 0033 y 0034 (el ente decide; el juicio es de conscience), ADR 0004 (eventos
D2), ADR 0015 (esquema de telemetria), ADR 0043 (`prompt.run` no enruta),
ADR 0052 (trace en `prompt.stream`), meta ADR 0007 (una integracion nueva es
configuracion, sin codigo).

Dispone `external_home_assistant CR-0001` (issue #51): **ACEPTADO, REFORMULADO**
en la forma (D1) y en la confianza en las anotaciones (D6). Acota lo decidido
en meta para el hito H09 (H09P7-H09P10), que no se reabre aqui.

## Contexto

El CR pide la primera frontera de herramientas del core: que el modelo del
dominio `domotica` pueda llamar, dentro del turno, a herramientas de una capa
externa servidor MCP, con una politica por `interlocutor_profile` y nada
destructivo. Se cumple la condicion de ADR 0022: hay una herramienta concreta.

Dos choques con el estado del core, vistos al leer el codigo de `v0.4.3`:

1. `ARCHITECTURE.md` pone `tool_contracts` bajo `reasoning_loop`. Pero el modo
   `directo` de extended, por donde entra la voz, llama a `prompt.stream`.
2. El CR habla del "perfil del dominio". En el core, `profiles[]` son juegos de
   parametros del modelo compartidos entre dominios: `domotica` usa `default`,
   como casi todos. Colgar ahi las herramientas se las daria a todos ellos.

Practica habitual contrastada: el agente de conversacion de Home Assistant, los
SDK de agentes (OpenAI Agents, el tool runner de Anthropic) y Open WebUI con
llamada nativa hacen el bucle de herramientas DENTRO de la llamada de chat, con
limite de vueltas, y declaran los permisos junto al agente especializado, no en
los parametros del modelo. La guia de "excessive agency" de OWASP para LLM pide
ofrecer al modelo solo lo permitido y comprobar de nuevo al invocar.

## Decision

### D1. El bucle vive en `prompt.*` y se declara en el dominio

`prompt.run` y `prompt.stream` ejecutan un bucle de herramientas SOLO cuando el
dominio resuelto declara `tools`. Un dominio sin `tools` sigue exactamente como
en `v0.4.3`: una llamada al modelo, una respuesta. `reasoning.*` y `task.*` no
ven herramientas en `v0.5.0`.

Configuracion (aditiva):

    tool_providers:
      home_assistant:                 # id del proveedor
        transport: streamable_http    # unico transporte en v0.5.0
        url: <del despliegue>
        auth_env: <NOMBRE_DE_VARIABLE>  # opcional; el secreto nunca va en el YAML
        timeout_s: 10                 # por llamada a herramienta

    domains:
      - id: domotica
        ...
        tools:
          provider: home_assistant
          max_rounds: 4
          allow:                      # por interlocutor_profile
            child: [<herramienta>, ...]
            adult: [<herramienta>, ...]
          deny: [<herramienta>, ...]  # opcional: endurece, nunca relaja

Reglas del validador: `provider` existe en `tool_providers`; las claves de
`allow` son perfiles validos de la identidad (`adult`, `child`); `max_rounds`
>= 1. Un `interlocutor_profile` vacio o sin entrada en `allow` no recibe
ninguna herramienta (denegar por defecto, ADR 0007).

Precision sobre `prompt.run` en `CORE_CONTRACT.md`: "una llamada, una
respuesta" pasa a "una peticion, una respuesta". Con herramientas, una peticion
puede hacer varias llamadas al modelo, pero sigue sin enrutar ni orquestar
(ADR 0043): el dominio lo fija quien llama.

Descartado: el bucle en `reasoning.run` (extended tendria que cambiar de
capacidad para la casa, y cada orden de voz pasaria por un bucle de pasos); las
herramientas en un perfil de parametros propio (la letra del CR: mezcla
parametros del modelo con permisos).

### D2. El cliente ve solo texto; sin eventos nuevos

El flujo de `prompt.stream` emite los mismos tipos de evento que hoy (`token`,
`done`, `error`). El texto que el modelo escriba en cualquier vuelta se envia
segun llega; las llamadas a herramientas y sus resultados nunca salen al
cliente. `done.trace` anade un unico campo aditivo, `tool_calls` (numero de
llamadas del turno, invocadas o no), que vale 0 en un dominio sin `tools`.

Descartado: un evento `step` por llamada (va mas alla del CR) y retener el texto
hasta la ultima vuelta (retrasa el primer token sin necesidad).

### D3. Rechazos y fallos legibles para el modelo

Una llamada que no pasa la politica (D6), o que falla al invocar (tiempo
agotado, error del proveedor, `isError` de MCP), vuelve al modelo como
RESULTADO de la herramienta, con un texto corto que puede explicar ("denegado:
<herramienta> no esta permitida para este interlocutor"). El turno sigue; el
cliente no recibe error.

Si el proveedor no responde al pedir la lista de herramientas, el turno sigue
sin herramientas y con una nota de sistema: las herramientas de la casa no
estan disponibles, dilo y no supongas estados. Motivo: sin ella el modelo de
`domotica` puede inventar el estado (criterio 6 de H09).

No hay tipos nuevos en `CoreError`.

### D4. Limite de vueltas y cierre que siempre responde

Una vuelta es una llamada al modelo. `max_rounds` (4 por defecto) cuenta las
vueltas que ofrecen herramientas. Si la ultima aun pide herramientas, el core
hace una llamada mas SIN herramientas, para que siempre haya respuesta, y lo
registra (D5, estado `limit`). Cada llamada a herramienta tiene su
`timeout_s` (10 por defecto). Varias llamadas pedidas en la misma vuelta se
ejecutan en el orden recibido.

Descartado: terminar con error al llegar al limite (la voz lo oiria como
averia) y dos vueltas fijas (no permite leer el estado y despues actuar).

### D5. Telemetria de cada llamada

Dos eventos de telemetria nuevos, internos (no son eventos D2 y no salen al
stream), con la identidad completa del request como el resto:

- `tools_offered`, uno por turno con herramientas: proveedor, perfil y lista
  ofrecida tras la politica. Hace comprobable el criterio 8 de H09 (denegar)
  aunque el modelo nunca pida lo prohibido.
- `tool_call`, uno por llamada: proveedor, herramienta, argumentos, estado
  (`invoked`, `denied`, `error`, `limit`), latencia, tamano del resultado y sus
  primeros 2 KB.

Las columnas del CSV no cambian (ADR 0015); proveedor y herramienta van en la
carga JSONL. `schema_version` no sube: los nombres de evento nuevos son
aditivos.

### D6. Politica: declarado, en lista y no destructivo

Antes de OFRECER y de nuevo antes de INVOCAR, una herramienta pasa si:

1. viene del proveedor declarado en el dominio;
2. esta en `allow[interlocutor_profile]` y no en `deny`;
3. no es destructiva para el core.

Destructiva se decide con las anotaciones MCP tal como las define la
especificacion: `readOnlyHint: true` o `destructiveHint: false` la hacen no
destructiva; sin anotaciones cuenta como destructiva (valores por defecto de
MCP). En `v0.5.0` lo destructivo no pasa para ningun perfil (H09P10): la
confirmacion humana de ADR 0007 se construira cuando un consumidor la necesite.

**Reformulacion del CR:** sobra la bandera `trust_annotations`. Declarar un
proveedor en `tool_providers` ES confiar en sus anotaciones; un servidor no
declarado nunca se consulta. La politica del core solo endurece (`deny`, y la
regla 3 no se desactiva), nunca relaja lo que marca la capa.

### D7. Cliente MCP

El core es cliente MCP con la libreria que ya usa para su servidor (`mcp`,
extra `interfaces`). Una sesion por turno: se abre al empezar el turno con
herramientas, pide `tools/list`, sirve las llamadas del turno y se cierra al
terminar. Sin cache entre turnos en `v0.5.0`. El transporte al backend de
modelos (ADR 0003) gana `tools` en la peticion y `tool_calls` en la respuesta,
en el formato OpenAI compatible.

## Impacto

- Contrato publico (`docs/VERSIONADO.md`): seccion de configuracion nueva y
  aditiva, campo aditivo `done.trace.tool_calls`, eventos de telemetria nuevos.
  En la serie pre-1.0 seria PATCH; se marca **MINOR (`v0.5.0`)** por su
  envergadura, como en el precedente de ADR 0034. Decision del usuario.
- Extended: sin eventos D2 nuevos, asi que no tiene nada que reenviar de mas.
  Consta el aviso (meta `REGISTRO_CAPAS.md` 2b).
- Borde: ninguno. Sigue rechazando `tools` del cliente (edge ADR 0002).
- Capa origen: `ia_nest_external_home_assistant` necesita `core >=0.5 <0.6`.

## Consecuencias

- `docs/FRONTERAS.md` (`tool_contracts`, `ia_nest_external_*`) y
  `docs/ARCHITECTURE.md` (el diagrama y las fichas de `reasoning_loop` y
  `tool_contracts`) se reescriben con esta forma.
- `docs/CORE_CONTRACT.md`: la precision de D1 en `prompt.run` y el campo de D2.
- ADR 0022 queda cumplido para `tool_contracts`; ADR 0007 sigue vigente, con la
  confirmacion humana aplazada (H09P10).
- Criterio falsable para la entrega, con un proveedor MCP de prueba en el
  laboratorio:
  1. un dominio sin `tools` responde igual que en `v0.4.3` (`tool_calls: 0`,
     sin `tools_offered`);
  2. `child` recibe solo su lista; una herramienta de `adult` no aparece en
     `tools_offered` y, llamada a la fuerza, consta como `denied`;
  3. una herramienta sin anotaciones o con `destructiveHint: true` no se
     ofrece a ningun perfil;
  4. una orden permitida cambia el estado del proveedor de prueba y consta
     como `invoked` con sus argumentos;
  5. con el proveedor caido, el turno responde con un aviso legible y sin
     estado inventado;
  6. un modelo que pide herramientas sin parar se corta en `max_rounds` y
     responde con texto (`limit`);
  7. el cliente de `prompt.stream` no recibe ningun tipo de evento nuevo.
