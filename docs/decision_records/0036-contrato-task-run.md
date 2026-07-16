# Decision 0036: contrato de task.run (orquestacion multi-modelo, linea v0.2)

Fecha: 2026-07-16

## Decision

Se fija el contrato de `task.run`, la capacidad de orquestacion multi-modelo
del core (ADR 0034), antes de implementarla (fase v0.2-1 del PLAN).

**Flujo (5 etapas, todas observables):**

1. PLAN: un modelo planificador descompone la tarea en subtareas, cada una con
   pista de dominio.
2. ROUTE: cada subtarea se resuelve con el router y la precedencia existente
   (ADR 0019).
3. FAN-OUT: subtareas independientes en paralelo (con tope configurable),
   dependientes en secuencia; cada subtarea es un `prompt.run` con la
   identidad propagada.
4. COMBINE: un modelo combinador funde los resultados.
5. EVALUATE: valora el combinado y decide terminar o iterar, dentro de
   limites. Puede RE-EJECUTAR (volver a 3) o RE-PLANIFICAR (volver a 1);
   cada via tiene su propio contador en los limites.

**Checkpoints:** eventos del flujo D2 (ADR 0004/0015), consumidos desde el dia
uno por CLI/REST/MCP y telemetria (leccion de ADR 0035: ninguna costura sin
consumidor): `task_received`, `plan_ready`, `subtask_done` (por subtarea),
`combine_ready`, `iteration_end`, `task_done`. La semantica de VETO
(conscience bloquea/replantea en un checkpoint) es extension futura (ADR 0034);
los puntos de anclaje quedan definidos aqui.

**Cortes tipados** (patron de `reasoning.run`): `task_done | max_subtasks |
max_iterations | max_time | max_context_tokens | error`.

**Config declarativa:** nueva seccion `orchestration` (ADR 0016): `planner` y
`combiner` se declaran por referencia a un modelo O a un dominio, con perfil
propio; limites por defecto (`max_subtasks`, `max_iterations`,
`max_replans`, `max_time_s`, `max_context_tokens`) y `max_parallel`.

**Telemetria:** cada subtarea traza con `task_id` y vinculo al request padre;
el arbol completo de la tarea es reconstruible (insumo del modo sueno de
conscience, ADR 0034).

**Paridad:** `ianest task run` / REST (SSE) / MCP, via la capa de servicio.

## Motivo

La orquestacion es la evolucion del core como "orquestador local de modelos"
(ADR 0034, `VISION_FUNCIONAL.md`). Fijar el contrato antes de implementar
mantiene la disciplina de v0.1 (bateria como criterio de aceptacion, fase
v0.2-2). Reusa registry, router, `prompt_runtime`, el patron refine de
`reasoning.run`, perfiles, errores tipados y telemetria; no toca los
adaptadores (ADR 0018) ni el caracter backend-agnostico (ADR 0003).

## Consecuencia

- `CORE_CONTRACT.md` incorpora `task.run` (contrato fijado; implementacion en
  fases v0.2-2/3). El contexto de identidad aplica tambien a `task.run`.
- Impacto de version: minor; version objetivo v0.2.0 (ADR 0034).
- Alternativas descartadas: nombre `orchestrate.run` (mas largo, sin ganancia);
  checkpoints como puertos de callback (leccion ADR 0035); planner fijo no
  configurable (contradice la config declarativa).
