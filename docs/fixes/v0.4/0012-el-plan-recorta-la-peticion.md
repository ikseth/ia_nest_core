# 0012: el planificador recorta la peticion y la cobertura no lo ve

Estado: aparcada (2026-10-20, reconciliada por el usuario); fuera de la tanda
v0.4.1
Tipo: calidad del planificador + hueco de declaracion
Impacto de version: por decidir (probablemente patch si llega a implementarse)
Version objetivo: ninguna todavia

Origen: hallazgo 2 de los avisos de `ia_nest_extended` del 2026-10-20
(`ia_nest_meta/docs/handoff/avisos_al_core_desde_extended_2026-10-20.md`).
Misma familia que la [ficha 0008](0008-requisitos-del-planificador-perdidos-y-no-declarados.md).

## Problema

Medido por extended en un hilo real: peticion de una lista de cenas "incluyendo
la receta". El plan sale con una sola subtarea, "crear una lista de cenas", y la
receta desaparece. `requirements_covered` sale `true`, porque los requisitos los
extrae el planificador EN LA MISMA RESPUESTA que el plan: si recorta el plan,
recorta tambien los requisitos, y la comprobacion cuadra consigo misma.

## Por que se aparca

1. **No esta reproducido en el core.** Era un segundo turno, y no se sabe que
   prompt exacto le llego al core tras la reescritura de extended. Sin eso no se
   puede saber si el recorte es del planificador o viene de arriba.
2. **El remedio de verdad no es un patch.** Para que la cobertura vea el recorte,
   los requisitos tienen que salir de la PETICION con independencia del plan, y
   eso es una llamada mas por tarea y una decision de diseno sobre PLAN.
3. **Es una afirmacion de calidad.** Cerrarlo exige un control externo a las
   senales del core (regla de criterio de salida de `docs/PLAN.md`), y eso pide
   su propia bateria de casos de respuesta conocida.

## Para reabrirla

- extended aporta el prompt exacto que recibio `task.run` en el caso medido;
- se reproduce contra el core, por el cable, con el planificador desplegado;
- si se reproduce, se disena la extraccion de requisitos independiente del plan,
  con su coste por tarea medido.
