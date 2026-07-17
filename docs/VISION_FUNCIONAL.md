# Vision funcional

Estado: validado (cuestionario inicial)

## Objetivo

IA_NEST Core debe ser, a la vez:

- orquestador local de modelos IA,
- nucleo para agentes,
- base de sistema inteligente,
- plataforma modular de integracion con servicios.

La consciencia no define el core basico. Es una capa superior de control,
evolucion y simulacion de IA consciente.

## Core minimo

El core minimo debe incluir:

- enrutado por dominios,
- seleccion de modelos,
- razonamiento iterativo controlado,
- MCP/API estable,
- evaluacion de calidad.

## Agentes

Los agentes quedan fuera del core.

Deben poder vivir en repos separados y consumir IA_NEST Core mediante contratos
estables.

## Extensiones

RAG y busqueda web pertenecen a `ia_nest_extended`.

La consciencia pertenece a una capa superior, previsiblemente
`ia_nest_core_conscience`.

Home Assistant pertenece a un modulo externo.

## Interfaces iniciales

El core debe exponer primero:

- CLI,
- MCP,
- API REST.

## Prioridad de modelos

Orden de importancia:

1. calidad,
2. rendimiento,
3. control local,
4. facilidad de cambio de modelos,
5. trazabilidad.

## Filosofia

Core pequeno y modulos externos.

## Planificacion

Fases estrictas con criterios de salida.

## Senales de buen rumbo

Orden de relevancia:

1. responde por CLI con modelos locales,
2. enruta dominios correctamente,
3. expone MCP usable,
4. puede ser usado por un agente externo,
5. cumple el conjunto anterior de forma integrada.

