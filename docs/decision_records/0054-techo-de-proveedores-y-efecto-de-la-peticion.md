# Decision 0054: proveedores como techo y efecto de la peticion

Fecha: 2026-11-20
Estado: aceptado por el usuario (2026-11-20)

Depende de: ADR 0053 (tool_contracts por MCP; D6, politica), ADR 0043
(`prompt.run` no enruta), ADR 0007 (denegar por defecto), meta ADR 0007
(regla 3: sin el campo nuevo, como antes), meta ADR 0018 (catalogo de
recursos: punto 2, techo; D5, efecto).

Dispone `extended CR-0006` (ia_nest_core#57), **tramo A, ACEPTADO** con el
ajuste de la capa origen del 2026-11-20 (meta H12P7, D1): el punto 1
(`catalog`, resumen y preseleccion) espera a meta `H13`. El tramo B se dispone
aparte.

## Contexto

Linea base de meta `H12` (H12P1b, 2026-11-19): por la voz, "que se esta viendo
ahora en el Kodi del salon?" acabo con `kodi_recomendar` poniendo una pelicula.
El turno ofrecia una accion que la pregunta no pedia (OWASP LLM06:2025). La
politica de ADR 0053, D6 filtra por perfil y por anotaciones, pero no por lo
que la peticion pide.

Ademas, ADR 0053, D6 hace de declarar un proveedor el acto de confianza. Meta
ADR 0018 lo separa: declarar es el techo (a que se puede conectar el ente y con
que secreto, lo pone la operacion) y la confianza es memoria, se guarda en
extended (extended ADR 0016) y la decide el operador.

## Decision

### D1. `turn_context` en `prompt.run` y `prompt.stream`

Parametro opcional nuevo, declarado en el catalogo de esas dos capacidades:

    "turn_context": {"trusted_providers": ["home_assistant"]}

Es un dato, no una instruccion: no llega al modelo. Sin el parametro, el core
se comporta como `v0.5.0` (meta ADR 0007, regla 3). Una parte desconocida
dentro de `turn_context` se ignora (el tramo B anadira `frame` y `H13`
`catalog`); un tipo invalido en una parte conocida es error de entrada.

### D2. `tool_providers` es el techo; se consulta la interseccion

Un turno con herramientas solo abre sesion con el proveedor del dominio si esta
en `tool_providers` (el techo, como hoy) y, cuando llega `turn_context`, ademas
en `trusted_providers`. Si no lo esta, el turno sigue sin herramientas, sin
abrir conexion, con la nota de sistema de proveedor no disponible, y
`tools_offered` registra `reason: "untrusted"`. Un nombre en
`trusted_providers` que no este en el techo no hace nada: la memoria solo
resta. Reformula ADR 0053, D6 ("declarar es confiar"): declarar es el techo.

### D3. Efecto de la peticion: `read` u `order`

Todo turno con herramientas clasifica, antes de ofrecerlas, el efecto de la
peticion con una llamada corta al modelo del enrutador (`config.router`; sin
enrutador, el modelo del dominio): `read` si pide saber, `order` si pide
cambiar algo. En la duda, o si la clasificacion falla o no se entiende,
`read`. Vale igual con dominio fijado o enrutado: se clasifica donde se
ofrecen las herramientas, y quien llama no puede imponer el efecto.

### D4. El efecto solo resta

Con `read` solo pasan las herramientas permitidas por D6 de ADR 0053 que ademas
traen `readOnlyHint: true`. Con `order`, lo permitido por D6, como hoy. El
efecto se comprueba al ofrecer y otra vez al invocar. `tools_offered` y
`done.trace` registran el efecto (`effect`) y su motivo.

### D5. `tool_provider.list`

Capacidad nueva de solo lectura: los ids de `tool_providers` del techo y los
dominios que usan cada uno, sin url, transporte ni secretos. Permite que
extended tome el techo del core en vez de declararlo dos veces (meta H12P6).

## Impacto

- Contrato (`docs/VERSIONADO.md`): parametro opcional nuevo, campos aditivos en
  la traza y en la telemetria, capacidad nueva y cambio de semantica de
  `tool_providers` cuando llega `turn_context`. **MINOR (`v0.6.0`)**.
- Coste declarado: una llamada mas al modelo del enrutador en cada turno con
  herramientas. Se mide con v1-ha.
- Extended: ya manda `turn_context` cuando el core lo declara (extended
  ADR 0016). Tomar el techo de `tool_provider.list` es trabajo suyo, despues.
- Borde: ninguno.

## Criterio falsable

1. Sin `turn_context`, un dominio con herramientas se comporta como en `v0.5.0`
   salvo por el efecto (D3 y D4).
2. Con `trusted_providers: []` no se abre sesion con ningun proveedor y
   `tools_offered` dice `untrusted`.
3. Un proveedor confiado que no esta en el techo no se consulta nunca.
4. "Que se esta viendo ahora en el Kodi del salon?" se clasifica `read`, y
   `kodi_recomendar` (sin `readOnlyHint`) ni se ofrece ni se invoca aunque el
   modelo la pida.
5. "Pon la luz del salon al 50 %" se clasifica `order` y ofrece lo de hoy.
6. Una clasificacion que falla da `read`.

## Lo que esta decision NO cubre

- El marco de la conversacion y preguntar como resultado declarado (tramo B).
- El resumen y la preseleccion del catalogo (meta `H13`).
- Acotar por clase de aparato (aplazado en meta ADR 0018, D5).
- La confirmacion humana de ADR 0007 (sigue aplazada).
