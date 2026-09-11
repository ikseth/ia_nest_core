# Linea de actuacion

## Fase actual

Definir y estabilizar el core antes de escribir integraciones.

## Secuencia obligatoria

1. Contexto IA.
2. Alcance del core.
3. Arquitectura minima.
4. Contratos internos.
5. Bateria de evaluacion (definir la bateria como criterio de aceptacion,
   antes de implementar; el motor `eval.run` que la ejecuta llega en fase 6+).
6. Implementacion minima.
7. Interfaces MCP y REST minimas (paridad con CLI).
8. Plan de repos/modulos externos.

## Criterio de avance

No se abre una fase nueva si la anterior no esta documentada y validada.

Que significa VALIDADA no lo fija este documento: es vocabulario comun del ente y
vive en `ia_nest_meta/docs/DOCTRINA_MULTI_IA.md`, regla de la puerta de
laboratorio (meta ADR 0010). En resumen, para no tener que abrir el otro fichero:
una fase que cambia comportamiento observable no cierra sin una ejecucion contra
un despliegue real, por la superficie que consumen las capas de encima, con
criterio declarado ANTES de medir, ejecutada en vez de narrada, y cruzada por dos
agentes.

Lo que este repo pone de su parte es el PROCEDIMIENTO: `deploy/smoke_rest.py`
para la superficie REST, la bateria de conformidad con su digest declarado, y el
criterio propio de cada fase del `PLAN`.

## Uso de IA

La IA puede proponer, revisar y codificar, pero no debe ampliar alcance por
inferencia. Cualquier ampliacion requiere decision registrada.

## Metodologia

- Aplicar steelman en decisiones relevantes.
- Preguntar antes de inferir puntos criticos.
- Preferir herramientas pequenas y componibles.
- Mantener nombres y atributos normalizados.
- Documentar scripts con cabecera basica.
- No crear abstracciones sin necesidad demostrada.
