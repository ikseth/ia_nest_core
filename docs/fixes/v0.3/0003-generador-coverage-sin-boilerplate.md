# 0003: generador de coverage sin boilerplate y cenido a sus unidades

Estado: implementada
Tipo: mejora (robustecimiento surgido del smoke real, patron v0.2-3)
Impacto de version: patch
Version objetivo: v0.3.0

## Problema

Smoke real del modo coverage (cine por decadas). Cada llamada de
generacion produce:

1. Preambulo y cierre conversacionales ("Por supuesto! A continuacion..."
   / "Espero que esta informacion sea de tu interes. Disfruta del cine!").
2. Contenido que desborda sus unidades asignadas: como el prompt del
   generador incluye el OBJETIVO COMPLETO del usuario, cada llamada intenta
   re-responder toda la tarea en vez de cenirse a sus unidades. De ahi el
   sangrado entre chunks (peliculas repetidas entre decadas, decadas
   cruzadas).

Como el modo coverage ensambla de forma determinista SIN combiner (por
diseno, ADR 0038), esos preambulos, cierres y solapamientos quedan visibles
como costuras en la respuesta final.

Es un defecto generico del prompt de generacion, backend-agnostico, no de
un modelo concreto (mismo criterio que las fichas v0.3/0001 y 0002).

## Cambio

`_coverage_generation_prompt` se constrine para que el generador emita SOLO
el contenido de sus unidades asignadas:

- sin preambulo, sin cierre, sin meta-comentario;
- estrictamente las unidades objetivo, sin abordar otras unidades ni el
  resto de la tarea;
- el objetivo global se conserva como CONTEXTO, marcado como tal, no como
  instruccion de responderlo entero.

No afecta a conformance (los fakes ignoran el texto del prompt): digest
`5aa67516...` estable.

## Criterios de aceptacion

- El prompt del generador incluye la instruccion de solo-contenido y
  cenido a las unidades objetivo (test de unidad sobre el texto del
  prompt).
- Re-smoke de laboratorio: los fragmentos ya no traen preambulo/cierre y no
  hay sangrado apreciable entre chunks (senal, sin exigir texto exacto).
- Conformance 34/34 con digest identico; pytest verde con y sin extras;
  sin dependencias nuevas.

## Archivos previstos

- `src/ianest_core/runtime/task_runtime.py`
- `tests/test_task_coverage.py`

## No cubre

La precision factual (agrupaciones erroneas, oscars ausentes, duplicados
del propio modelo) es calidad del modelo local 7B, no del orquestador.
Cenir el prompt reduce el sangrado entre chunks, pero la exactitud es cosa
del modelo o de una futura capa de verificacion (territorio de conscience,
no del core).

## Resultado

Implementado en `_coverage_generation_prompt`: el objetivo global queda
marcado como contexto, las unidades asignadas como unico contenido a producir
y se prohiben preambulo, cierre, transiciones, meta-comentario y contenido de
otras unidades. Se anadio una prueba unitaria del texto del prompt.

Verificacion automatizada: pytest 125/125 con extras; pytest 121/121 y 4
omitidos sin extras de interfaces; conformance 34/34 con digest
`5aa67516fb10c2a9b1040798262bc09231467f5bff02fe748a1f8b636ddd3475`.
El re-smoke de laboratorio queda fuera de esta ejecucion local.
