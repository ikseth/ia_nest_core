# 0002: retirada de tags de domain.route

Estado: implementada
Tipo: retirada de un parametro publico ya sin efecto (ejecuta ADR 0043)
Impacto de version: minor (desaparece un parametro de REST y de la firma MCP)
Version objetivo: v0.4.0 (tramo A)

## Problema

`domain.route` acepta `tags` por REST (`payload.get("tags", [])`) y por MCP
(`tags: list[str] | None = None`), y ese valor recorre la capa de servicio y el
runtime hasta `DomainRouter.route`, donde la primera instruccion es `del tags`.

No hace nada, y no lo hace desde ADR 0043: `tags` era del filtro de palabras
clave. Al retirar el keyword (fase 3b-ii) se conservo la FIRMA a proposito, para
no romper llamadas en mitad de la linea, y se anoto que el parametro quedaba
ignorado. Como con `routing_rules` (ficha v0.4/0001), lo que nunca se decidio fue
cuando termina esa tolerancia.

La CLI, en cambio, nunca expuso `tags`. De modo que la misma capacidad declara
tres superficies distintas: dos interfaces lo aceptan y lo tiran, y la tercera ni
lo menciona.

Lo encontro el gate del catalogo (fase v0.4-A3b): al exigir que `params`
coincida con las tres interfaces, el implementador paro y pregunto en vez de
inventar una respuesta. Es exactamente el trabajo para el que existe ADR 0046,
haciendose antes incluso de estar terminado.

## Cambio

Retirar `tags` de punta a punta:

- `rest.py`: deja de leerlo del cuerpo.
- `mcp_server.py`: sale de la firma de la herramienta `domain.route`.
- `service.route_domain`, `DomainRuntime.route` y `DomainRouter.route`: sale de
  las firmas y de la llamada encadenada, incluido el `del tags`.

No se anade `--tags` a la CLI: seria dar superficie publica nueva a un concepto
retirado.

Un cliente REST que siga enviando `tags` en el cuerpo no recibe error: el campo
simplemente deja de leerse, como cualquier clave desconocida. Quien use la
herramienta MCP con `tags` si vera un cambio de esquema, y por eso el impacto es
minor y no patch.

## Criterios de aceptacion

- `grep -rn "tags" src/` no encuentra rastro del parametro (salvo, si aparece,
  en contextos ajenos como `domain_tag` de identidad, que es otra cosa).
- `domain.route` responde igual que hoy por CLI, REST y MCP: mismo dominio,
  modelo, confianza y motivo.
- La herramienta MCP `domain.route` declara solo `prompt` e `identity`.
- El gate del catalogo pasa: `params` de `domain.route` coincide con las tres
  interfaces.
- Digest de conformidad INTACTO (`a60aa35b...`): ningun caso enruta por tags,
  porque no hacian nada. Si cambia, es que algo mas se movio.
- `pytest` en verde con y sin extras.

## Archivos previstos

- `src/ianest_core/rest.py`, `mcp_server.py`, `service.py`
- `src/ianest_core/runtime/domain_runtime.py`, `src/ianest_core/domain_router.py`
- tests que pasen `tags`
- `CHANGELOG.md`

## No cubre

- Anadir `--tags` a la CLI.
- El alias `runtime detect`, que es cosa distinta: llama al mismo servicio que
  `runtime.health` (`health` es literalmente `return detect_runtime(...)`) y solo
  cambia el render de la CLI. Se conserva como alias declarado en el catalogo,
  con su render propio en codigo.

## Resultado

Implementada junto al gate que la destapo (fase v0.4-A3b, parte 1). `tags` sale
de `rest.py`, `mcp_server.py`, `service.route_domain`, `DomainRuntime.route`,
`DomainRouter.route` -incluido el `del tags`- y del ejecutor de evaluacion de
`domain.route`. La herramienta MCP `domain.route` declara ya solo `prompt` e
`identity`, y el gate bidireccional lo comprueba.

Las unicas apariciones de `tags` que quedan en `src/` son del endpoint
`/api/tags` del provisioner de Ollama, que es otra cosa.

Verificacion independiente: 249 tests con extras, 242 y 7 skips sin extras,
conformidad 90/90 y digest `a60aa35b` INTACTO, como se esperaba de un parametro
que no hacia nada.
