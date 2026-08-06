# Decision 0038: cobertura como criterio de completitud semantica en task.run

Fecha: 2026-07-23

## Decision

`task.run` incorpora un modo de ejecucion explicito, seleccionado por el
consumidor (linea v0.3). No hay promocion automatica entre capacidades ni
entre modos.

- `mode=pipeline` (default): flujo de 5 etapas del ADR 0036, sin cambios.
- `mode=coverage`: completar tareas con unidades enumerables y verificables
  mediante generacion incremental guiada por cobertura.

La completitud se separa en dos senales independientes:

- finalizacion tecnica: `finish_reason` (`stop | length | error`), senal
  cruda del backend (ficha v0.2/0002);
- finalizacion semantica: `coverage_complete` (`true | false`), decidida
  solo por el ledger de cobertura, nunca por `finish_reason`.

**Flujo del modo coverage:**

1. DERIVE: el planner deriva unidades de cobertura (id, descripcion
   verificable, `domain_hint` opcional, `depends_on` opcional, orden
   requerido). `max_subtasks` actua como techo de unidades derivables.
2. GENERATE: cada llamada usa ventana nueva, se enruta por la precedencia
   del ADR 0019 y cubre un subconjunto acotado (`units_per_chunk`) de
   unidades pendientes con dependencias satisfechas; grupos independientes
   en paralelo (`max_parallel`). El prompt lleva el objetivo, las unidades
   objetivo y el resumen compacto del ledger (ids completados +
   referencias minimas), nunca el texto integro aceptado.
3. VALIDATE: un rol `validator` declarativo (referencia a modelo o dominio
   con perfil, como planner/combiner) mapea el fragmento producido a los
   ids realmente cubiertos. No se acepta la auto-declaracion del
   generador.
4. Emision: fragmentos aceptados como `answer_chunk` (en orden, con
   retencion de prefijo contiguo) y snapshot compacto del ledger como
   `coverage_updated`. Ambos son adiciones al catalogo de eventos D2
   (ADR 0004).
5. ASSEMBLE: respuesta final por concatenacion determinista en el orden
   requerido. Sin reescritura global por un combiner: reintroduciria la
   ventana unica que motiva esta decision. `combine_ready` marca el
   ensamblado.

`finish_reason=stop` con cobertura pendiente continua; `length` es senal
fuerte de continuacion desde lo pendiente, sin duplicar lo aceptado.

**Ledger:** estado temporal de la ejecucion (objetivo, unidades,
completadas, pendientes, fallidas, orden, referencias minimas, contadores,
limites). No es memoria y no depende de `ia_nest_extended`. El texto
integro de los fragmentos vive en el resultado y en telemetria JSONL.

**Cortes tipados aditivos:** `max_chunks | max_total_tokens | no_progress`.
`no_progress` dispara tras `max_no_progress_iterations` ciclos sin delta
de cobertura o cuando todas las pendientes agotaron
`max_retries_per_unit` (el detalle queda en el ledger final). `task_done`
implica `coverage_complete=true`. `max_time` y `error` se conservan.
`max_total_tokens` es acumulado de la tarea; `max_context_tokens`
(pipeline) no cambia.

**Config declarativa aditiva** (`orchestration.coverage`, ADR 0014/0016):
`validator`, `units_per_chunk`, `max_chunks`, `max_total_tokens`,
`max_retries_per_unit`, `max_no_progress_iterations`. Los limites globales
de `orchestration` aplican tambien al modo coverage.

**EVALUATE/replan no participan en modo coverage v1:** el ledger subsume el
juicio done/rerun/replan. Re-derivar unidades a mitad de tarea queda
diferido sin caso demostrado (anti-entropia).

**Seleccion de capacidad:** sigue siendo explicita del consumidor; los
criterios de uso se documentan en `CORE_CONTRACT.md`. No hay promocion
silenciosa de `prompt.run` a `task.run`. Una capacidad clasificadora
consultiva (`capability.route`, analoga a `domain.route`: propone, no
ejecuta) queda registrada como diferida y no se construye sin consumidor
real (leccion MemoryPort, ADR 0035).

**Bateria de aceptacion** (fija el blanco antes de implementar; casos 1-14
conformance con fakes, 15 smoke real):

1. Diez unidades cubiertas a razon de tres por llamada terminan las diez.
2. `finish_reason=stop` con cobertura incompleta provoca continuacion.
3. `finish_reason=length` continua desde lo pendiente, sin duplicados.
4. Ninguna unidad aparece duplicada en la respuesta final.
5. El orden requerido se conserva (aceptacion desordenada incluida).
6. Cada unidad se enruta al dominio y modelo declarados (ADR 0019).
7. Un fallo reintenta solo las unidades afectadas.
8. Unidades independientes se ejecutan en paralelo (`max_parallel`).
9. Las dependientes (`depends_on`) se ejecutan en orden.
10. Falta de progreso produce corte `no_progress` con parcial conservado.
11. `max_chunks`, `max_time` y `max_total_tokens` no se sobrepasan.
12. Streaming y bloqueante producen el mismo contenido final.
13. La telemetria JSONL permite reconstruir cobertura, fragmentos y
    modelos usados.
14. Los casos 1-13 corren solo con adaptadores fake.
15. Smoke real: generacion incremental demostrada por umbral
    (`coverage_complete=true`, `chunk_index >= 2`), sin texto exacto.

## Motivo

Incidente reproducible: una peticion con requisitos enumerables produjo
respuesta incompleta con `finish_reason=stop` (829 de 4096 tokens). No fue
agotamiento fisico: el modelo dio por terminada una respuesta
semanticamente incompleta. El core ya distingue la finalizacion tecnica
(ficha 0002) pero carece de concepto de finalizacion semantica. El
`task.run` v0.2 solo tiene un juicio global ternario (done/rerun/replan):
`rerun` rehace todo el fan-out sin acumulacion, el combiner regenera la
respuesta entera en una ventana unica, no hay dedup ni orden garantizado,
ni reintento por subtarea, ni corte de no-progreso.

Alternativas descartadas: subir limites o instruir el prompt (no toca la
causa; contra el principio de no ajustar por caso); enriquecer EVALUATE
sin ledger (sin garantias de dedup/orden ni telemetria reconstruible);
capacidad separada nueva (duplicaria PLAN/ROUTE/FAN-OUT y superficie
publica; la cobertura es un criterio de terminacion de la orquestacion,
no otra clase de cosa; su steelman se recupera haciendo la evolucion
aditiva por modo con default intacto); resolverlo en un agente externo
(necesita registry/router e identidad por unidad: es core por el criterio
del principio 4).

## Consecuencia

- `CORE_CONTRACT.md` incorpora el modo coverage y la seccion de seleccion
  de capacidad. Impacto de version: minor; objetivo v0.3.0 (por
  envergadura, precedente ADR 0034; decision del usuario 2026-07-23).
- El digest de conformance v0.2 (modo pipeline) debe permanecer identico;
  la bateria v0.3 declara digest propio.
- Los consumidores de streaming deben tolerar tipos de evento y valores de
  `stop_reason` desconocidos; la regla se hace explicita en el contrato.
- CSV de telemetria: 18 columnas congeladas (ADR 0015); todo el detalle de
  cobertura vive en JSONL (insumo directo para pulse, ADR 0037).
- La contabilidad real de tokens en los cortes de `task.run` se adelanta
  como ficha independiente (v0.2.x, ficha v0.2/0003).
- Sin persistencia ni reanudacion tras desconexion del cliente:
  limitacion aceptada; si algun dia se exige, sera decision estructural
  aparte.
- Riesgos asumidos y mitigaciones: bucles (triple guardia retries /
  no_progress / max_chunks), duplicados (ledger como fuente de verdad +
  validador), perdida de orden (ensamblado determinista), evaluacion
  erronea del validador (rol declarativo separado + smoke; validadores
  deterministas por tipo de unidad quedan como evolucion), crecimiento
  del ledger (solo ids y referencias minimas viajan a ventanas
  siguientes).
