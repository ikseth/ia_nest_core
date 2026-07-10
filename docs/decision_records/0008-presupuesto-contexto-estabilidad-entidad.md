# Decision 0008: presupuesto de contexto como estabilidad de la entidad

Fecha: 2026-07-10

## Decision

El presupuesto de contexto/tokens del `reasoning_loop` es una cuestion de
rendimiento y estabilidad de la entidad simulada, no de coste/pago (los
modelos son locales). El bucle trata la ventana de contexto como recurso
cognitivo limitado, junto a los limites de iteraciones y tiempo. Al
acercarse al limite, para o compacta segun politica declarada, y lo
registra en la traza. Nunca desborda la ventana de forma silenciosa.

## Motivo

En un core que simula un "ente", el limite existe para que la entidad se
mantenga coherente y no degrade su razonamiento al saturar la ventana.

## Consecuencia

Lo que cae fuera del contexto de trabajo (por compactacion o limite) es el
candidato natural a persistir en memoria; vincula con la frontera de memoria
(ADR 0011). Detalle en `ARCHITECTURE.md` (D6).
