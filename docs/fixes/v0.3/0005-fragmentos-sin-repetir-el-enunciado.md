# 0005: fragmentos que no repiten el enunciado de su unidad

Estado: implementada
Tipo: mejora (residuo reabierto de la ficha 0003)
Impacto de version: patch
Version objetivo: v0.3.0

## Problema

Los fragmentos del modo coverage repiten el enunciado de su unidad como frase
introductoria. Evidencia de laboratorio (2026-08-05, ocho planetas):

    chunk 1  'Mercurio'
    chunk 2  'El segundo planeta del sistema solar es Venus.'
    chunk 3  'El tercer planeta del sistema solar es la Tierra.'
    chunk 4  'El cuarto planeta del sistema solar es Marte.'
    ...

Siete de los ocho fragmentos empiezan reformulando la pregunta. Como el modo
coverage ensambla sin combiner (por diseno, ADR 0038), el resultado final
repite la misma muletilla ocho veces y el usuario lo lee como respuesta
repetida.

Ademas es INCONSISTENTE: la unidad 1 respondio `Mercurio` a secas y las otras
siete en frase completa. El mismo modelo, el mismo prompt de generacion, dos
formatos.

Es el residuo que la ficha 0003 dejo anotado sin resolver: "los fragmentos
conservan formato HETEROGENEO entre si -unos titulan '1920s:', otros repiten el
prompt de la unidad como pregunta-". La ficha 0003 elimino preambulos, cierres
y meta-comentario, pero no la reformulacion del enunciado, que es un cuarto
patron distinto.

## Cambio

`_coverage_generation_prompt` gana una restriccion explicita: no reformular el
enunciado de la unidad ni convertirlo en frase introductoria; emitir
directamente el contenido que la unidad pide.

Las prohibiciones actuales (preambulo, cierre, transicion, meta-comentario,
contenido de otras unidades, no repetir completadas) se conservan sin cambio.

## Criterios de aceptacion

- El texto del prompt de generacion incluye la restriccion de no reformular el
  enunciado (test de unidad sobre el texto del prompt, patron de la ficha 0003).
- Conformance sin cambio de digest: los fakes ignoran el texto del prompt, como
  en la ficha 0003.
- Re-smoke de laboratorio con el caso de los ocho planetas: los fragmentos no
  empiezan reformulando la unidad, y el formato entre fragmentos es
  apreciablemente mas homogeneo (senal, sin exigir texto exacto).
- pytest en verde con y sin extras; sin dependencias nuevas.

## Archivos previstos

- `src/ianest_core/runtime/task_runtime.py`
- `tests/test_task_coverage.py`

## No cubre

- La homogeneizacion de FORMATO del resultado final (titulos, vinetas, tono)
  sigue siendo la pasada de "voz del ente" diferida en `CAPAS_FUTURAS.md`, que
  merece su propia decision. Esta ficha reduce una causa concreta de
  heterogeneidad; no la cierra.
- La exactitud factual del modelo. En la misma ejecucion de laboratorio, la
  unidad 5 respondio "Marte" donde correspondia Jupiter y el validador la
  acepto: `coverage_complete` acredita cobertura, no verdad (ADR 0038,
  ADR 0025). Territorio de `ia_nest_core_conscience`.
- El separador entre fragmentos, que es la ficha 0004 de esta misma linea.

## Resultado

Implementada con una restriccion explicita en el prompt de generacion y test
del texto del prompt.
