# 0002: parser de ids cubiertos tolerante al formato del validador

Estado: implementada
Tipo: correccion (robustecimiento surgido del smoke real, patron v0.2-3)
Impacto de version: patch
Version objetivo: v0.3.0

## Problema

Smoke real del modo coverage con un validador `mistral_nemo` (tarea de
humanidades: obras maestras del cine por decadas). El validador devolvio
la cobertura como un diccionario con los ids de unidad como CLAVES y el
contenido como valores:

    {"decada_1920": [{"nombre_original": "Nosferatu", ...}], ...}

`_parse_covered_ids` solo aceptaba una lista de ids o un dict con una
clave-envoltorio conocida (`ids`, `unit_ids`, `completed_units`,
`covered`). Ante ese dict-por-id devolvia conjunto VACIO: ninguna unidad
se aceptaba, dos ciclos sin progreso y corte `no_progress` con respuesta
vacia. El modo funcionaba con un validador que emitia lista (el smoke de
los planetas usaba `qwen_tech`), pero no es razonable exigir un unico
formato a modelos locales heterogeneos: devolver "dict id -> contenido"
es una lectura valida de "valida la cobertura".

Es un hueco de robustez del orquestador, backend-agnostico, no un defecto
de un modelo concreto (mismo criterio que la ficha v0.3/0001).

## Cambio

`_parse_covered_ids` extrae ids cubiertos de todas las formas que emiten
los modelos locales, delegando en un helper `_covered_ids_from`:

- lista de strings (formato original);
- lista de objetos con `id` o `unit_id`;
- dict con clave-envoltorio (`ids` | `unit_ids` | `completed_units` |
  `covered`): se desciende recursivamente;
- dict cuyas CLAVES son los ids cubiertos: se toman las claves.

La generosidad es segura: el llamador
(`_validate_coverage_generation`) ya intersecta los ids devueltos con las
unidades objetivo pendientes, asi que ids espurios no se aceptan.

## Criterios de aceptacion

- `_parse_covered_ids` acepta lista, lista de objetos, dict-envoltorio y
  dict-por-id; devuelve vacio ante texto no parseable (tests
  parametrizados).
- Un run de coverage con validador que emite dict-por-id completa la
  cobertura (test end-to-end con `ScriptedFakeAdapter`).
- La bateria de conformance v0.3 no cambia de digest
  (`5aa67516...`): los fakes usan formato lista, no afectados.
- pytest completo en verde con y sin extras; sin dependencias nuevas.
- Re-smoke de laboratorio con validador `mistral_nemo` dentro de umbral.

## Archivos previstos

- `src/ianest_core/runtime/task_runtime.py`
- `tests/test_task_coverage.py`

## Resultado

Implementado en `fix/v0.3-0002-covered-ids-parser`:

- `_covered_ids_from` cubre las cuatro formas; 115 tests en verde,
  conformance 34/34 con digest identico.
- Re-smoke de laboratorio: (pendiente de anotar tras la ejecucion).
