# Decision 0034: orquestacion multi-modelo en el core; conscience como supervisor dual

Fecha: 2026-07-16

## Decision

**Orquestacion.** La orquestacion multi-modelo de tareas (descomponer una tarea
compleja, repartirla a varios modelos -fan-out-, combinar resultados e iterar
sobre el conjunto) es capacidad FUTURA del CORE (linea v0.2), como evolucion
natural de `domain.route` + `reasoning.run`. No vive en `ia_nest_agents`
(descartado, ADR 0033) ni en `ia_nest_core_conscience` (descartado: el
supervisor no ejecuta el pensar que supervisa).

El diseno v0.2 nace con PUNTOS DE SUPERVISION incorporados: checkpoints
observables (y vetables) en la entrada/salida del orquestador y entre
iteraciones, para que conscience pueda intervenir sin redisenar el motor.

**Conscience.** Se define como SUPERVISOR etico/de personalidad, con dos modos:

- Modo live (tiempo real): supervisa los checkpoints del flujo; puede bloquear
  o replantear cuestiones que le generen duda, contrastando con una memoria/RAG
  etica.
- Modo sueno (batch): apaga el core (capacidad administrativa de quiesce,
  futura, con su propio ADR) y revisa la actividad del dia sobre la telemetria
  (JSONL para el detalle, CSV para agregados) para contextualizar, aprender y
  generar nuevas tramas de memoria.

**Sedimentacion.** Las resoluciones de conscience (debates eticos/de
personalidad) se persisten como memoria de comportamiento -un tier/namespace de
la memoria de `ia_nest_core_extended`- y vuelven al core via enriquecimiento
(system prompt por perfil ADR 0025, contexto ADR 0031). La personalidad del
ente se sedimenta; el motor no se toca.

## Motivo

El usuario define conscience como ente supervisor cuyas resoluciones van
definiendo el comportamiento del core (idea presente en el ia_nest original,
no explicitada hasta ahora en el core). La vision da al core la identidad de
"orquestador local de modelos IA". La base ya esta preparada: eventos D2
(`token/step/trace/done/error`, ADR 0004/0018) como puntos de observacion,
cortes tipados de `reasoning.run` como costuras temporales, y telemetria
CSV+JSONL con identidad por request (ADR 0010/0015) como diario del ente.

## Consecuencia

- La linea v0.2 del core se abrira con su propio plan y ADRs de detalle
  (contrato de orquestacion, checkpoint de supervision, quiesce). Nota de
  versionado: pese a ser adicion compatible, por su envergadura se marcara
  como MINOR (v0.2.0); decision del usuario en la reconciliacion (ADR 0030).
- Orden de capas confirmado: `extended` primero (la memoria etica de conscience
  necesita su infraestructura de memoria), conscience despues.
- La memoria -incluida la etica- vive en `extended` (via 2, ADR 0031);
  la retirada de `MemoryPort` del core (supersede parcial de ADR 0011) se
  registrara con el cambio de codigo correspondiente.
- Alternativas descartadas: orquestacion en agents (ADR 0033); conscience como
  funcion ejecutiva del pensar (propuesta previa de Claude, retirada).
