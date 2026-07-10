# Decision 0011: frontera de memoria (costura), sin implementar memoria

Fecha: 2026-07-10

## Decision

El core minimo NO implementa memoria. Define solo la costura: un puerto
`MemoryPort` (patron puertos-y-adaptadores) con `NullMemoryAdapter` (no-op)
por defecto. El nombre `Port` deja explicito que es una frontera hacia fuera,
no una capacidad interna del core.

La identidad de segmentacion (`user_id`, `service`, `session_id`,
`domain_tag`, `namespace`) viaja en el request y en la traza en las
capacidades de usuario/sesion/razonamiento, aunque la memoria sea nula. Las
capacidades administrativas o de introspeccion no la requieren. En uso local
existe una identidad local configurada por defecto (no anonima). La
estrategia real de memoria vive en un modulo externo (previsiblemente
`ia_nest_core_extended` o dedicado).

## Motivo

Ampliacion de alcance registrada (regla anti-entropia): D6 (ADR 0008)
obliga a responder a donde va el contexto evacuado; la respuesta es memoria.
Definir la costura ahora elimina la deuda de redisenar `reasoning_loop` y
`prompt_runtime` mas tarde, sin violar el no-objetivo de memoria avanzada
(la implementacion por defecto no recuerda nada).

## Consecuencia

- `CORE_CONTRACT.md` incorpora el contexto de identidad del request, acotado
  a las capacidades de usuario/sesion/razonamiento.
- La telemetria (ADR 0010) incluye esos campos para que traza y memoria
  compartan identidad.
- Lecciones de la cantera `ia_nest` que la costura respeta (documentadas en
  `ARCHITECTURE.md`, "Frontera de memoria"): tiers realmente distintos,
  separar scope de lectura y escritura, consistencia de `namespace` entre
  escritura y lectura.
- Fuera de la costura y del core: niveles concretos, consolidacion por
  hitos, doble conciencia, RAG, esquema de almacenamiento.
