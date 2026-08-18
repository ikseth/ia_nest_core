# 0008: los requisitos del planificador se pierden por la forma, y nadie lo dice

Estado: propuesta
Tipo: robustez del runtime + hueco de declaracion
Impacto de version: patch
Version objetivo: v0.4.x

## Problema

Medido en laboratorio con `qwen2.5:7b` como planificador. El core le pide, con
estas palabras:

    "Return only a JSON object with requirements and subtasks. Requirements must
     be objects with string id and text. Subtasks must have prompt, covers as a
     list of requirement ids..."

Y el modelo devuelve **todo lo que se le pide**:

    {
      "requirements": { "req1": "...", "req2": "...", "req3": "..." },
      "subtasks": [
        { "prompt": "...", "covers": ["req1"], "domain": "codigo" },
        { "prompt": "...", "covers": ["req2"], "domain": "codigo" },
        { "prompt": "...", "covers": ["req3"], "domain": "matematicas" }
      ]
    }

Los requisitos estan. Los `covers` estan. La descomposicion es correcta.

Pero el core pidio una **lista** de objetos con `id` y `text`, y el modelo
devolvio un **mapa** de `id` a texto. Misma informacion, otra forma. El parser
espera lista, recibe diccionario, y el resultado es **cero requisitos**.

## Lo que cuesta esa perdida

Cuatro cosas, en cadena:

1. **Los requisitos desaparecen.** `requirements: []`.
2. **El enlace de cobertura desaparece con ellos.** Los `covers` que el modelo si
   emitio no tienen donde colgarse: sin requisitos no hay `covered_by`. Nota para
   no confundirse: que `covers` no aparezca dentro de `plan[]` es CORRECTO, ADR
   0048 lo movio a `requirements[].covered_by`. Lo que se pierde es el enlace,
   no su sitio.
3. **Se paga una renegociacion entera.** Como `requirements_covered` es falso, el
   core reintenta pidiendo al planificador que declare requisitos. El modelo
   responde igual de bien y con la misma forma, asi que se vuelve a descartar. En
   la traza se ven los dos intentos (`plan_attempts` 1 y luego 2) y la etapa PLAN
   tarda unos 8 s en vez de la mitad.
4. **No se declara nada.** Al agotar los intentos, el bucle sale sin anadir
   ninguna degradacion.

## La asimetria, que es el hueco de verdad

    plan SUMINISTRADO por el consumidor, sin requisitos
        -> {stage: plan, reason: requirements_unavailable, action: skip_coverage_check}

    plan DERIVADO por el planificador, sin requisitos
        -> nada

`requirements_unavailable` solo se emite en `_supplied_plan_resolution`. La via
del planificador no tiene equivalente, asi que el mismo hecho -no hay requisitos
con los que comprobar cobertura- se declara por una via y se calla por la otra.

Lo que el consumidor recibe es `requirements_covered: false` sin explicacion. Es
deducible cruzando tres campos -`requirements` vacio y `uncovered_requirements`
vacio-, pero deducir no es declarar, y el criterio de este repo es que un hecho
que importa se dice.

## Relacion con las otras fichas, sin generalizar de mas

- Con [ficha v0.4/0006](0006-router-tolerante-a-la-respuesta-del-modelo.md)
  comparte **familia**: un parser estricto descarta una respuesta valida por su
  forma. Son sitios distintos y arreglos distintos; no se refunden.
- Con [ficha v0.4/0007](0007-task-plan-no-publica-sus-degradaciones.md) es
  **complementaria, y el orden importa**: aquella hace que `task.plan` PUEDA
  publicar degradaciones; esta hace que HAYA una que publicar. Arreglar solo la
  0007 no destapa este caso: `task.plan` seguiria devolviendo `degradations: []`,
  porque en la via del planificador no se anade nada.

## Cambio

Dos medidas, y la segunda vale aunque la primera no se haga.

### 1. Aceptar el mapa de requisitos

El parser acepta `requirements` tanto como lista de `{id, text}` como mapa de
`id` a texto, que es la otra forma natural de escribir lo mismo. Se normaliza a
la forma de lista antes de seguir; el contrato publico no cambia.

Precedente directo: [ficha v0.3/0001](../v0.3/0001-derive-coverage-tolerante.md)
hizo exactamente esto en DERIVE cuando el planificador real devolvio `"id": 1`
como entero.

### 2. Declarar cuando no hay requisitos, venga el plan de donde venga

Si tras agotar los intentos no hay requisitos, la via del planificador emite la
MISMA degradacion que la via del plan suministrado:

    {stage: plan, reason: requirements_unavailable, action: skip_coverage_check}

Una sola forma para un solo hecho. La tarea sigue terminando bien: una
degradacion no es un corte.

## Lo que NO se hace

- **No se inventan requisitos** a partir de las subtareas. Si el planificador no
  los da, no los hay.
- **No se amplia el catalogo de cortes tipados.** Esto es degradacion, no corte.
- **No se quita la renegociacion.** Con la medida 1 deja de dispararse por este
  motivo; si se dispara por otro, sigue siendo util.

## Criterios de aceptacion

- Caso de conformidad: planificador que devuelve `requirements` como mapa ->
  se normalizan, `requirements_covered` se evalua de verdad y NO hay
  renegociacion por requisitos ausentes.
- Caso de conformidad: planificador que nunca declara requisitos -> tras agotar
  intentos, `degradations` contiene `requirements_unavailable`, con la misma
  forma que en la via del plan suministrado.
- Caso de conformidad: la via del plan suministrado sigue comportandose
  exactamente igual que hoy.
- El digest de conformidad se mueve por los casos nuevos y se DECLARA.
- En laboratorio, el mismo prompt de tres partes produce 3 requisitos con su
  `covered_by`, y la etapa PLAN baja de dos llamadas al planificador a una. Se
  anotan los dos numeros.

## Archivos previstos

- `src/ianest_core/runtime/task_runtime.py`
- `eval/battery/v0.4/plan.yaml`, `eval/README.md`
- `CHANGELOG.md`

## No cubre

- La forma en que el core PIDE el plan, que es correcta y no se toca.
- El modo `coverage`, que tiene su propia contabilidad.
- La eleccion del modelo planificador, que es configuracion del operador.

## Resultado

Pendiente.
