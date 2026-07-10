# Decision 0009: adoptar antes que construir infraestructura estandar

Fecha: 2026-07-10

## Decision

No se desarrolla lo que ya existe como estandar open-source maduro. Para
piezas de infraestructura (servidor MCP, framework API/REST, backends de
modelos, contenedores) se adopta una solucion existente y el core aporta
configuracion declarativa, scripts de instalacion/personalizacion y
documentacion. Se construye solo el valor diferencial: orquestacion,
dominios, evaluacion y las fronteras del core.

## Motivo

Ahorro de desarrollo cuando el componente adoptado aporta mas que su coste.

## Consecuencia

Heuristica: adoptar si es estandar con varias implementaciones, no exige
fork ni mantenimiento pesado, y se puede envolver tras un contrato fino
propio (patron adaptador, como en ADR 0003). Candidatos: SDK oficial MCP,
framework API estandar, Ollama/llama.cpp/vLLM, imagenes de contenedor
existentes. Por ser transversal, puede promoverse ademas a principio en
`IA_NEST_CORE_CONTEXT.md` / `CONVENCIONES.md`. Detalle en `ARCHITECTURE.md`
(D7).
