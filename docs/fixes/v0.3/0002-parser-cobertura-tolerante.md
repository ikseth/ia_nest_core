# 0002: robustez del contrato de validacion de cobertura

Estado: implementada
Tipo: correccion (robustecimiento surgido del smoke real, patron v0.2-3)
Impacto de version: patch
Version objetivo: v0.3.0

## Problema

Smoke real del modo coverage con validador `mistral_nemo` (tarea de
humanidades: obras maestras del cine por decadas). El modo terminaba con
cobertura vacia (`no_progress`, respuesta vacia) por dos defectos
encadenados del contrato de validacion, ambos genericos y
backend-agnosticos (mismo criterio que la ficha v0.3/0001):

1. El validador, en vez de devolver los ids cubiertos, REESCRIBIA todo el
   contenido (titulos, directores, oscars) como JSON grande. Ese JSON
   excedia el `max_tokens` del perfil y llegaba TRUNCADO, con lo que no
   parseaba y no se acreditaba ninguna unidad.
2. Aun cuando el JSON llegaba entero, algunos modelos lo devolvian como
   diccionario con los ids de unidad como CLAVES y el contenido como
   valores (`{"1920s": [...], ...}`), formato que el parser no aceptaba.

## Cambio

Dos caras del mismo problema:

- **Prompt del validador** (`_validate_coverage_generation`): se le da la
  lista exacta de ids objetivo y un ejemplo, y se le exige devolver SOLO
  un array JSON de ids, sin titulos ni contenido. Asi la respuesta es
  corta y no se trunca. No afecta a conformance (los fakes ignoran el
  prompt), digest estable.
- **Parser** (`_parse_covered_ids` via helper `_covered_ids_from`):
  extrae ids de todas las formas que emiten los modelos locales:
  - lista de strings (formato original);
  - lista de objetos con `id` o `unit_id`;
  - dict con clave-envoltorio (`ids` | `unit_ids` | `completed_units` |
    `covered`): se desciende recursivamente;
  - dict cuyas CLAVES son los ids cubiertos: se toman las claves.

La generosidad del parser es segura: el llamador ya intersecta los ids
devueltos con las unidades objetivo pendientes, asi que ids espurios no
se aceptan.

## Criterios de aceptacion

- `_parse_covered_ids` acepta lista, lista de objetos, dict-envoltorio y
  dict-por-id; devuelve vacio ante texto no parseable (tests
  parametrizados).
- Un run de coverage con validador que emite dict-por-id completa la
  cobertura (test end-to-end con `ScriptedFakeAdapter`).
- La bateria de conformance v0.3 no cambia de digest (`5aa67516...`).
- pytest completo en verde con y sin extras; sin dependencias nuevas.
- Re-smoke de laboratorio con validador `mistral_nemo` dentro de umbral.

## Archivos previstos

- `src/ianest_core/runtime/task_runtime.py`
- `tests/test_task_coverage.py`

## Resultado

Implementado en `fix/v0.3-0002-covered-ids-parser`:

- Prompt del validador constrenido a devolver solo ids; parser tolerante
  a las cuatro formas. 115 tests en verde, conformance 34/34 con digest
  identico.
- Re-smoke de laboratorio (planner y validador `mistral_nemo`, prompt de
  cine por decadas): `task_done`, `coverage_complete=true`, 9/9 unidades,
  chunk_index 3, generacion enrutada a `general/mistral_nemo`
  (occidental), 56.6s. Los dos smokes fallidos previos (dict-por-id
  truncado y JSON de plan invalido de qwen) quedan resueltos: el primero
  por esta ficha, el segundo por mover el planner a mistral (ajuste de
  config del lab). Detalle en local/lab/2026-07-23_coverage_smoke.md.
