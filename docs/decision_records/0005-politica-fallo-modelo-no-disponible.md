# Decision 0005: politica de fallo ante modelo no disponible

Fecha: 2026-07-10

## Decision

Cada dominio declara `modelo_preferido` y una lista opcional
`modelos_alternativos`. Si el preferido no esta disponible, el router
intenta la lista en orden. Si ninguno esta disponible, devuelve error
tipado `ModelUnavailable`, nunca un fallback silencioso a un modelo no
declarado. La sustitucion efectiva se registra en la traza del request.

## Motivo

Preserva la trazabilidad (principio 5) y evita sorpresas de calidad por
sustitucion silenciosa de modelo.

## Consecuencia

`domain_router` depende del estado de disponibilidad de `model_registry` /
`runtime.health`. Detalle en `ARCHITECTURE.md` (D3).
