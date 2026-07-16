# Decision 0035: retirada de MemoryPort (supersede parcial de ADR 0011)

Fecha: 2026-07-16

## Decision

Se retira del core la costura de memoria: `MemoryPort`, `NullMemoryAdapter`,
el parametro `memory` de `prompt_runtime` y la llamada `read_context`.

SE CONSERVA la otra mitad de ADR 0011, que es la valiosa: la identidad de
segmentacion (`user_id`, `service`, `session_id`, `domain_tag`, `namespace`)
viajando en cada request y traza. Esa identidad es la clave con la que
`ia_nest_core_extended` indexara su memoria.

## Motivo

Decision de enriquecimiento en la capa (via 2, ADR 0031/0033/0034): la memoria
-incluida la etica de conscience- vive ENCIMA del core, en extended, que arma
el prompt y hace el write-back con la respuesta. El puerto quedo sin proposito:
`read_context` se llamaba descartando el resultado, y `write`/`record_milestone`
no se invocaban desde ningun sitio. ADR 0011 temia el coste de redisenar
`prompt_runtime` mas tarde; con la via 2 ese rediseno nunca ocurrira, porque el
runtime no necesita conocer la memoria.

Leccion registrada (aplicada a la linea v0.2): una costura sin consumidor real
se pudre. Los checkpoints de orquestacion (ADR 0034) se disenan como eventos y
cortes que el propio core consume desde el dia uno.

## Consecuencia

- `src/ianest_core/memory/` se elimina; `prompt_runtime` pierde el parametro
  `memory`; tests que lo referencien se ajustan.
- `ARCHITECTURE.md` (frontera de memoria) se alinea: la estrategia y la
  ejecucion viven en extended; el core aporta la identidad.
- Impacto de version: patch (interno; `MemoryPort` no era capacidad del
  contrato publico de `CORE_CONTRACT.md`). Entrada en `CHANGELOG.md`.
- ADR 0011 queda parcialmente superada: costura retirada, identidad vigente.
