# 0007: `task.plan` repliega en silencio cuando el planificador devuelve algo ilegible

Estado: propuesta
Tipo: hueco de contrato (adicion compatible)
Impacto de version: patch
Version objetivo: v0.4.x

## Problema

Medido en laboratorio con modelos reales. `task.plan` con este prompt:

    "Necesito tres cosas independientes: 1) una definicion de kernel,
     2) un script bash que cuente ficheros por extension,
     3) la derivada de x cubo"

devuelve, de forma repetible:

    subtareas: 1
    requisitos: 0
    dominio: general
    plan[0].prompt: el prompt original ENTERO

Y la respuesta completa solo trae `plan`, `requirements`, `effort`, `params` y
`trace`. **Ninguna senal de que algo fuera mal.**

No es que el planificador decidiera una sola subtarea. Es el repliegue del core
cuando no puede leer la respuesta del planificador, en `task_runtime.py`:

    plan = [{"prompt": prompt, "domain": self.config.default_domain or "general"}]
    ...
    degradations.append(
        {"stage": "plan", "reason": "unparseable_shape", "action": "single_subtask"}
    )

La firma encaja exacta con lo medido: una subtarea, el prompt original completo y
el dominio por defecto.

**El core hace lo correcto: lo detecta y lo DECLARA.** El problema es quien puede
verlo:

    TaskRunResult.to_dict()   incluye "degradations"
    TaskPlanResult            NO tiene el campo, ni en la clase ni en to_dict()

O sea que `task.run` publica la degradacion y `task.plan` no puede, porque su
tipo de resultado no la lleva.

## Por que importa mas de lo que parece

Rompe las dos reglas que ordenan este tramo del diseno:

1. **ADR 0048**: "la respuesta de `task.plan` ES la peticion de `task.run`". Si
   una via declara la degradacion y la otra no, la simetria esta incompleta
   justo donde mas duele: en el momento de decidir si ese plan sirve.
2. **La regla del usuario**: "dentro de `plan[]` no vive nada cuya perdida sea
   silenciosa". Aqui lo que se pierde no es un campo: es la descomposicion
   entera, y se pierde sin dejar rastro en la respuesta.

Y el consumidor previsto es `ia_nest_extended`, que va a llamar a `task.plan`,
enriquecer cada subtarea con su RAG y devolver el plan a `task.run`. Con este
hueco recibe **una** subtarea que parece una decision legitima del planificador,
la enriquece, la reenvia y obtiene un resultado peor sin que nada haya fallado a
ojos de nadie. El fallo aparece como "el ente responde flojo", que es la clase de
sintoma que cuesta semanas atribuir.

## Cambio

`TaskPlanResult` gana `degradations`, con la misma forma y el mismo contenido que
en `task.run`, y `task.plan` lo publica siempre -lista vacia cuando no hay-.

Es adicion compatible: ningun campo existente cambia de nombre, tipo ni
significado.

`CORE_CONTRACT.md` lo declara en la seccion de `task.plan`, y dice explicitamente
que una lista vacia significa "sin degradaciones", no "no se sabe".

## Lo que esta ficha NO resuelve

Que el planificador real devuelva algo ilegible con esta frecuencia es otro
problema, de la misma familia que
[ficha v0.4/0006](0006-router-tolerante-a-la-respuesta-del-modelo.md): un parser
estricto contra un modelo que no siempre produce lo que se le pide. Esta ficha
solo se ocupa de que **se vea**.

El orden importa y es deliberado: primero que el hueco sea visible, despues
decidir cuanta tolerancia se le da al parseo. Al reves, se afina un parser sin
poder medir si mejora.

## Criterios de aceptacion

- Caso de conformidad: planificador que devuelve una forma ilegible ->
  `task.plan` responde con una subtarea Y con
  `{stage: plan, reason: unparseable_shape, action: single_subtask}` en
  `degradations`.
- Caso de conformidad: planificador correcto -> `degradations` es lista vacia,
  presente en la respuesta.
- Paridad: el campo viaja por CLI, REST y MCP, saliendo del catalogo.
- La forma de `degradations` es identica a la de `task.run`; una sola forma, no
  una por capacidad.
- El digest de conformidad se mueve por los casos nuevos y se DECLARA.
- En laboratorio, el mismo prompt de tres partes muestra la degradacion en vez de
  esconderla.

## Archivos previstos

- `src/ianest_core/runtime/task_runtime.py`
- `docs/CORE_CONTRACT.md`
- `eval/battery/v0.4/plan.yaml`, `eval/README.md`
- `CHANGELOG.md`

## No cubre

- La tolerancia del parseo del plan, que es su propia decision.
- `mode=coverage`, que tiene su propia contabilidad.
- La calidad del planificador o la eleccion de su modelo, que es del operador.

## Resultado

Pendiente.
