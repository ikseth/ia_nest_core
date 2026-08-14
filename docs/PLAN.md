# Plan

Estado: activo
Version: 1.1 - 2026-07-10 (auditado con Codex, reconciliado)

Fases segun `LINEA_DE_ACTUACION.md`. Regla: no se abre una fase sin validar
la anterior. Cada fase tiene criterio de salida falsable. Este documento no
acumula ideas sin decision.

## Fases 1-4: completadas

- Fase 1 Contexto IA: `IA_NEST_CORE_CONTEXT.md` (validado).
- Fase 2 Alcance: `ALCANCE_CORE.md` (validado).
- Fase 3 Arquitectura minima: `ARCHITECTURE.md` v0.8 (validado; ADRs 0003-0011).
- Fase 4 Contratos internos: `CORE_CONTRACT.md` + contexto de identidad
  (validado).

## Fase 5: Bateria de evaluacion (completada)

Estado: validada 2026-07-11. Artefactos en `eval/` (README, fixtures,
battery) y ADR 0017 (formato de resultados).

Objetivo: definir la bateria como CRITERIO DE ACEPTACION antes de
implementar, no como evaluacion de una implementacion ya hecha. Fija el
blanco para que la fase 6 no derive por inferencia.

Aclaracion: "bateria de evaluacion" aqui significa el conjunto de casos y el
veredicto esperado que la implementacion debera satisfacer. El motor que la
ejecuta (`eval.run`) se implementa en fase 6+ y consume esta bateria.

Dos pistas de evaluacion, separadas para no confundir determinismo con
calidad:

- Conformance determinista: casos ejecutados contra adaptadores FAKE. Salida
  reproducible bit a bit. Valida pipeline, ruteo, formato de traza y logica
  de veredicto. Es lo que da el veredicto "reproducible".
- Smoke de calidad: casos ejecutados contra un modelo local REAL. No dan
  veredicto reproducible (hay no-determinismo de muestreo); dan una senal de
  calidad y latencia dentro de umbrales.

Entregables:
- Conjunto declarativo de casos, etiquetados por pista (conformance | smoke),
  sin depender de servicios externos complejos.
- Formato de resultados de `eval.run` fijado (por caso: pista, veredicto,
  latencia, modelo usado, dominio usado).

Criterio de salida:
- Bateria escrita y revisada, con ambas pistas cubiertas.
- Cada caso de conformance tiene veredicto esperado reproducible.
- Cada caso de smoke tiene umbral de aceptacion (no veredicto exacto).
- Formato de resultados congelado.
- No requiere ejecucion (todavia no hay motor).

## Fase 6: Implementacion minima

Se parte en dos cortes para respetar "piezas pequenas". Cada corte tiene
criterio de salida propio.

### Fase 6a: vertical minimo de inferencia (completada)

Objetivo: el corte end-to-end mas fino posible (senal #1 de
`VISION_FUNCIONAL.md`: "responde por CLI con modelos locales").

Cadena: CLI -> prompt_runtime -> ModelAdapter (OpenAI-compatible, ADR 0003)
-> backend de desarrollo (ADR 0013), con modelo/dominio DECLARADO
explicitamente (sin router todavia; `prompt.run` admite dominio declarado por
contrato). Incluye identidad (default local configurado), traza minima
(CSV+JSONL, ADR 0010/0015) y `NullMemoryAdapter` conectado (no-op, ADR 0011)
para no crear deuda.

Criterio de salida:
- `prompt.run` responde por CLI con un modelo real en el backend de
  desarrollo (smoke de calidad).
- Genera traza por request con identidad.
- La pista de conformance de la bateria pasa contra adaptador fake, con
  veredicto reproducible.

### Fase 6b: ruteo, resiliencia y runner de evaluacion (completada)

Objetivo: completar el core minimo operable (senal #2: "enruta dominios").

Anade: `domain_router` (reglas declarativas), politica de fallo de modelo
(ADR 0005), `config.validate` minimo, y el runner que ejecuta la bateria de
fase 5 (semilla de `eval.run`).

Criterio de salida:
- `domain.route` selecciona dominio/modelo por reglas y lo registra en traza.
- Politica de fallo (ADR 0005) verificada con al menos un caso: preferido no
  disponible -> alternativo -> error tipado.
- `config.validate` detecta una configuracion invalida.
- El runner ejecuta la bateria completa: conformance reproducible + smoke con
  umbrales.

## Fase 7: Interfaces MCP y REST minimas (completada)

Objetivo: exponer las capacidades del vertical por MCP y REST sin logica
distinta a la CLI (regla de paridad de `CORE_CONTRACT.md`). MCP usa el SDK
oficial (ADR 0009) con version declarada y verificable (ADR 0006); REST usa
un framework estandar (ADR 0009). La CLI de fase 6 es la referencia de
comportamiento.

Criterio de salida:
- Un cliente MCP externo ejecuta `prompt.run` con paridad a CLI.
- Un cliente REST ejecuta `prompt.run` con paridad a CLI.
- `runtime.health` declara la version MCP y es verificable.
- Ninguna de las dos capas contiene logica de negocio (misma capa de nucleo).

## Fase 8: Bucle de razonamiento (reasoning.run) (completada)

Objetivo: implementar `reasoning.run` (CORE_CONTRACT): razonamiento iterativo
controlado y observable, SIN invocar herramientas (ADR 0022).

Alcance:
- Iteracion con limites: iteraciones, tiempo y presupuesto de contexto/tokens
  (ADR 0008), configurables por perfil (ADR 0014).
- Salida observable por paso (eventos `step` del flujo D2, ADR 0004/0015).
- Capacidad de desactivar pasos no necesarios.
- Se expone por CLI/REST/MCP via la capa de servicio (paridad).
- Reutiliza prompt_runtime, adaptadores, identidad y telemetria.

Fuera de esta fase: invocacion de herramientas (tool_contracts, diferido).

Criterio de salida:
- `reasoning.run` corta por cada limite (iteraciones, tiempo, tokens) y lo
  registra en traza.
- Salida observable por paso.
- Casos de conformance deterministas (FakeAdapter) para los cortes.
- Paridad CLI/REST/MCP; pytest en verde; core minimo instalable sin extras.

## Fase 9: Scripts de instalacion y deteccion de runtime/GPU (completada)

Objetivo: cerrar el punto de `ALCANCE_CORE.md` y del checklist "core cerrado".

Alcance:
- Script de instalacion (venv + `pip install -e .`; extras de interfaz
  opcionales).
- Deteccion de runtime/GPU (nvidia-smi / backend disponible), integrada con
  `runtime.health`.
- Cabecera humana/IA en scripts no triviales (CONVENCIONES).
- Repo publico: sin datos internos versionados; endpoints por env var.

Criterio de salida:
- Instalacion reproducible desde cero, documentada y verificada.
- `runtime.health` refleja la deteccion de runtime/GPU.
- Scripts con cabecera y sin secretos.

## Validacion en laboratorio (previa a fase 10) (superada)

Estado: superada 2026-07-14. Core validado end-to-end en hardware real (host
de laboratorio con RTX 3060, Ollama): install.sh, deteccion GPU,
config.validate, prompt.run, reasoning.run, ruteo por dominio (con criterio
anti-sesgo y fallback occidental), eval smoke, y las tres interfaces
(CLI/REST/MCP). 3 fixes menores aplicados y verificados: auto-carga de .env,
domain.route expone substituted/preferred_model, y system prompt por perfil
(ADR 0025, resuelve modelos que respondian en otro idioma).

Registro detallado y detalles del host: en `local/lab/` (no versionado).

## Fase 10: Plan de repos/modulos externos (completada)

Estado: completada 2026-07-15. Fronteras de handoff hacia las capas externas
documentadas en `docs/FRONTERAS.md` (memoria->extended; conciencia/modelo de
control->conscience; integraciones->external_*; agentes->agents; monitorizacion
->ops). Concerns futuros registrados en `docs/CAPAS_FUTURAS.md`.

Criterio de salida (cumplido):
- Contratos de frontera documentados y versionados (`docs/FRONTERAS.md`).
- Checklist "Core cerrado significa" de `IA_NEST_CORE_CONTEXT.md` cumplido
  (fase 9) y validado en laboratorio.

## Mejoras posteriores al cierre

El core quedo cerrado tras la fase 10. Mejoras acordadas despues, cada una con
su ADR:

- Provisioning de modelos (ADR 0029): `ianest model pull` descarga los modelos
  declarados que falten (capacidad opcional, backend-especifica).

## Linea v0.2 (abierta 2026-07-16)

Objetivo: orquestacion multi-modelo de tareas con supervision incorporada
(ADR 0034). Version objetivo: v0.2.0 (MINOR por decision del usuario,
ADR 0034). Misma disciplina que v0.1: fases con criterio de salida falsable,
diseno y bateria ANTES de implementar. Leccion de MemoryPort aplicada: los
checkpoints se disenan como eventos/cortes que el propio core consume desde el
dia uno, no como puertos a la espera de un consumidor futuro.

### Fase v0.2-0: limpieza de MemoryPort (completada 2026-07-16)

Retirar la costura muerta (ADR 0035): puerto, adaptador nulo y llamada
`read_context`; la identidad de segmentacion SE CONSERVA (clave de la memoria
de extended).

Criterio de salida: pytest verde con y sin extras; docs alineados
(ARCHITECTURE, frontera de memoria); CHANGELOG actualizado.

### Fase v0.2-1: contrato de orquestacion (completada 2026-07-16)

Disenar `task.run`: descomposicion, fan-out multi-modelo, combinacion,
iteracion; checkpoints observables (flujo D2) y cortes tipados; config
declarativa (planner, combiner, limites). ADRs de detalle + actualizacion de
`CORE_CONTRACT.md`.

Criterio de salida: contrato reconciliado por el usuario (con revision ciega
de Codex si aplica) y registrado.

### Fase v0.2-2: bateria de evaluacion v0.2 (completada 2026-07-16; enmienda task_subtask_unknown_hint aprobada)

Casos de conformance deterministas para orquestacion (ScriptedFakeAdapter
multi-modelo: plan, fan-out, combinacion, cada corte tipado) y smoke con
umbrales.

Criterio de salida (cumplido): 16 casos congelados en
`eval/battery/v0.4/plan.yaml.frozen`, tests requeridos declarados en
`eval/README.md`, digest sin mover.

### Fase v0.2-3: implementacion minima y validacion (completada 2026-07-16)

Validada en laboratorio: conformance 23/23 (digest declarado) y smoke 3/3 con
modelos reales (orquestacion completa en ~37s). Dos robustecimientos surgidos
del smoke real: parseo tolerante de plan/decision y domain_hint consultivo.

Vertical minimo de `task.run` con paridad CLI/REST/MCP y telemetria por
subtarea (task_id + vinculo al request padre).

Criterio de salida: conformance reproducible en verde; smoke en laboratorio;
core minimo instalable sin extras.

### Fase v0.2-4: quiesce administrativo (diferida 2026-07-16)

`runtime pause/resume` como capacidad administrativa (util para mantenimiento;
requerida por el modo sueno de conscience, ADR 0034). Decision del usuario al
cerrar v0.2-3: DIFERIDA hasta sembrar conscience (leccion de MemoryPort: sin
consumidor real, no se construye). La linea v0.2 se publica como v0.2.0 sin
quiesce.

En paralelo (fuera de este plan): tras cerrar v0.2-1, sembrar la definicion de
`ia_nest_extended` contra el contrato ya fijado.

## Linea v0.3 (abierta 2026-07-23)

Objetivo: completitud semantica guiada por cobertura en `task.run`
(`mode=coverage`, ADR 0038). Version objetivo: v0.3.0 (MINOR por
envergadura, precedente ADR 0034; decision del usuario). Misma disciplina:
bateria congelada antes de implementar; el modo pipeline y su digest de
conformance v0.2 permanecen intactos.

Metodo de trabajo de la linea: diseno, prompts por tarea y supervision por
Claude Code; implementacion por Codex sobre el contrato ya reconciliado
(no aplica modo ciego: se implementa una decision registrada, no se
propone diseno).

### Fase v0.3-0: contrato y ADR (completada 2026-07-23)

ADR 0038 registrado; `CORE_CONTRACT.md` (modo coverage + seleccion de
capacidad) y CHANGELOG actualizados; ficha v0.2/0003 (contabilidad real
de tokens) abierta como adelanto independiente.

Criterio de salida (cumplido): diseno reconciliado por el usuario
(2026-07-23) y registrado.

### Fase v0.3-1: config y bateria v0.3 (completada 2026-07-23)

Esquema `orchestration.coverage` (schema + validator + fixtures) y
bateria determinista congelada como `coverage.yaml.frozen` (el runner
hace rglob desde v0.2-3; el sufijo sustituye al "aparcar en
subdirectorio" de v0.2-2): 11 casos conformance (ADR 0038: 1-6, 9, 10,
11a/b/c) y los casos 3/7/8/12/13/14 como tests pytest requeridos en
eval/README. Enmienda de reconciliacion: `max_subtasks: 12` en la
fixture (los casos de 10 unidades eran insatisfacibles con el 4
heredado; detectado por el implementador antes de codificar).

Criterio de salida (cumplido): `config.validate` acepta/rechaza; casos
congelados antes de tocar el runtime; digest v0.2 sin cambio.

### Fase v0.3-2: implementacion minima (completada 2026-07-23)

Ledger, bucle DERIVE/GENERATE/VALIDATE/ASSEMBLE, eventos `answer_chunk`
(en orden, retencion de prefijo) y `coverage_updated` (JSONL), cortes
`max_chunks | max_total_tokens | no_progress`, reintentos por unidad,
ensamblado determinista y paridad CLI/REST/MCP (`--mode coverage`).
Bateria integrada (rename `.frozen` -> `.yaml`): conformance 34/34 con
digest recalculado y DECLARADO (ADR 0017, patron v0.2-3); el digest
v0.2 queda como historico en eval/README.

Criterio de salida (cumplido): conformance 34/34 con digest declarado;
pipeline byte a byte intacto; pytest verde con y sin extras; core
minimo instalable sin extras.

### Fase v0.3-3: validacion en laboratorio (completada 2026-07-23)

Smoke real (caso 15) en el host de laboratorio: task_done,
coverage_complete=true, chunk_index=6 (umbral >=2), 8/8 unidades, con
aceptacion desordenada real y orden conservado. Un robustecimiento
surgido del smoke, registrado como ficha v0.3/0001 (DERIVE tolerante a
ids no-string + granularidad explicita), patron v0.2-3.

Criterio de salida (cumplido): smoke dentro de umbral; ficha
registrada. El corte de v0.3.0 queda a decision del usuario en la
reconciliacion.

## Linea v0.4 (propuesta 2026-07-27; ampliada 2026-08-14)

Objetivo doble mas un saldo pendiente, en tramos independientes que se publican
juntos:

- **Tramo A**: cerrar `extended CR-0002` (ADR 0046) con un catalogo unico de
  capacidades del que se derivan las interfaces, y la capacidad
  `capability.list`. Incluye la unica ruptura de la linea: `task.run` pasa a
  JSON y su flujo se muda a `task.stream` (enmienda D5-a).
- **Tramo B**: cerrar `extended CR-0001` (ADR 0040, enmendado por ADR 0047)
  llevando hasta el nivel de subtarea la costura de entrada que el core ya tiene
  -el prompt-, sin abrir ninguna costura hacia arriba. La descomposicion se
  queda en el core; el enriquecimiento, en la capa.
- **Tramo C**: retirar `routing_rules` del esquema de configuracion, que ADR
  0043 dio por retirada y la linea del router dejo tolerada
  ([ficha v0.4/0001](fixes/v0.4/0001-retirada-de-routing-rules.md)).

Orden: A antes que B; C es independiente y puede ir en cualquier momento de la
linea. `task.plan` anade capacidad, ruta REST, herramienta MCP y
subcomando CLI; con el catalogo ya en pie, aterriza dentro de el y su paridad
queda verificada por el gate. Al reves habria que rehacerla.

Version objetivo: v0.4.0. Las dos son adiciones compatibles (PATCH por
`meta POLITICA_SEMVER.md` seccion 3); el usuario corta MINOR por envergadura,
como en v0.2.0 y v0.3.0. Misma disciplina: contrato y bateria ANTES de
implementar.

### Fase v0.4-A1: contrato del catalogo (completada 2026-08-14)

ADR 0046 reconciliado; `CORE_CONTRACT.md` actualizado (`capability.list`,
`core_version` en `runtime.health`, variante bloqueante de `task.run` por REST).

Criterio de salida (cumplido): decision reconciliada por el usuario y
registrada; `extended CR-0002` movido a `aceptado` en `ia_nest_meta`, con
respuesta por handoff.

### Fase v0.4-A2: bateria del catalogo (completada 2026-08-14)

Casos de conformance deterministas, congelados: `capability.list` enumera las
capacidades declaradas con su proyeccion por interfaz y su orden determinista;
una capacidad con hueco declarado lo devuelve nulo; `core_version` coincide con
el manifiesto; `identity` y `streaming` correctos; parametros con sus `choices`
y defectos.

Los tests del GATE (rutas REST construidas, subcomandos CLI construidos y firmas
MCP escritas, los tres contra el catalogo) y la equivalencia
`/task/run` JSON contra `/task/stream` SSE se DECLARAN aqui en `eval/README.md`
como tests pytest requeridos, y se escriben en la fase A3: no son expresables en
la bateria declarativa, y no pueden existir antes que el catalogo.

Criterio de salida (cumplido): 9 casos congelados en
`eval/battery/v0.4/capability.yaml.frozen`, tests requeridos declarados en
`eval/README.md`, digest sin mover.

### Fase v0.4-A3a: catalogo y capacidad (completada 2026-08-14)

`capabilities.py` como fuente unica (15 entradas); tabla de rutas REST derivada
de el; `capability.list` con paridad CLI/REST/MCP; `core_version` derivado de los
metadatos del paquete y publicado tambien en `runtime.health`; alineacion de
nombres de la enmienda D5-a (`task.run` bloqueante en `POST /task/run`,
`task.stream` con el SSE); ejecutor de evaluacion para las formas de `expect`
del catalogo; bateria integrada (90 casos) con digest declarado.

Criterio de salida (cumplido): conformance 90/90 con digest declarado; el render
de `ianest task run` intacto; pytest en verde con y sin extras.

### Fase v0.4-A3b1: catalogo completo y gates (completada 2026-08-14)

Lo que queda para que el catalogo sea fuente unica de verdad y no solo de
lectura: el parser de `argparse` se construye recorriendo el catalogo, y un test
de conformidad aserta que los nombres y las firmas de las herramientas MCP
coinciden con el (el gate de ADR 0046).

Decision pendiente que este tramo tiene que fijar: las banderas de RENDER de la
CLI (`--json`, `--quiet`, `--verbose`) no son parametros de la capacidad y hoy
no estan en el catalogo. Como el generador tiene que saber cuales lleva cada
accion -y `task.run` lleva `--quiet`/`--verbose` pese a no ser `streaming`-, el
catalogo necesita declararlo explicitamente en su proyeccion CLI.

Incluye la retirada de `tags` de `domain.route`
([ficha v0.4/0002](fixes/v0.4/0002-retirada-de-tags-de-domain-route.md)), que el
propio gate destapo: dos interfaces lo aceptaban y lo tiraban, y la tercera ni lo
mencionaba.

Criterio de salida (cumplido): el catalogo declara `metavar`, `description`,
`epilog`, `flags` y todos los parametros de cada capacidad; los gates de CLI y
MCP comparan en las dos direcciones -incluidos los textos, normalizando
`%(default)s`- y pasan contra las interfaces escritas a mano; `tags` retirado;
digest sin mover.

### Fase v0.4-A3b2: generar el parser (completada 2026-08-14)

Sustituir la construccion a mano de `_build_parser` por una que recorra el
catalogo. El render sigue siendo codigo, elegido por nombre de accion: lo que se
genera es el parser, no la presentacion. Los gates de A3b1 son la red que prueba
que la ayuda no se degrada.

Criterio de salida (cumplido): ninguna accion de CLI escrita a mano y despacho
por tabla; las 26 ayudas del binario identicas byte a byte a las de antes del
cambio; gates y tests de ayuda en verde sin tocarlos; digest sin mover.

Con esto el tramo A queda COMPLETO: el catalogo es la fuente unica de la que se
derivan la CLI y las rutas REST, contra la que se asertan las herramientas MCP, y
de la que responde `capability.list`.

### Fase v0.4-B1: contrato del plan explicito (completada 2026-08-14)

Fijado en `CORE_CONTRACT.md`: capacidad `task.plan` (solo la etapa PLAN, devuelve
el plan con el dominio ya resuelto y no ejecuta nada); entrada opcional `plan`
en `task.run`; corte tipado `replan_unavailable`; campo `plan_source`
(`planner | supplied`) en el checkpoint `plan_ready`. Alcance `mode=pipeline`.

ADR 0040 no era implementable tal cual: se escribio antes de ADR 0041, 0044 y
0045, que cambiaron la etapa PLAN por debajo. ADR 0047 lo enmienda con las tres
reglas que faltaban (esfuerzo heredado del plan, presupuesto concedido al plan
suministrado, requisitos que viajan con el plan o degradacion declarada) y el
contrato las incorpora.

Criterio de salida (cumplido): contrato reconciliado por el usuario (ADR 0040 y
ADR 0047) y registrado.

### Fase v0.4-B2: bateria de evaluacion (completada 2026-08-14)

Casos de conformance deterministas: plan suministrado valido; plan invalido de
forma (`PlanParseError`); plan con ciclo o indice invalido
(`PlanDependencyError`); plan que excede `max_subtasks`; decision `replan` con
plan suministrado -> corte `replan_unavailable`; `plan_source` correcto en las
dos vias; y no regresion (sin `plan`, salida identica a la actual).

Casos anadidos por ADR 0047 y ADR 0048: peticion con `plan`, `requirements` y
`effort` como campos hermanos, echo de lo que devolvio `task.plan`; plan
suministrado con `effort` explicito menor corta `max_subtasks`; sin `effort`,
`default_effort` con su cifra visible en `params.effort`; presupuesto concedido
sobre plan suministrado; plan sin `requirements` emite la degradacion
`requirements_unavailable`; `plan_attempts=0` con `plan_source=supplied`.

Criterio de salida (cumplido): 16 casos congelados en
`eval/battery/v0.4/plan.yaml.frozen`, tests requeridos declarados en
`eval/README.md`, digest sin mover.

### Fase v0.4-B3a: runtime del plan explicito (completada 2026-08-14)

La etapa PLAN como capacidad propia y la entrada de plan: `task.plan`, las
entradas `plan`, `requirements` y `effort` de `task.run`, el corte
`replan_unavailable`, `plan_source` en `plan_ready` y la inversion de la
cobertura (`covers` sale de `plan[]`, los requisitos ganan `covered_by`), con la
bateria integrada y el digest recalculado y DECLARADO: cambia la forma de un
evento publico, y esta anunciado en ADR 0048.

### Fase v0.4-B3b: paridad de interfaces

`task.plan` entra en el catalogo de capacidades y de ahi salen su subcomando, su
ruta REST y su herramienta MCP; la entrada de plan se declara como parametro. El
plan viaja por FICHERO en la CLI (ADR 0040: un plan como argumento de linea de
comandos es hostil). Tests de paridad declarados en `eval/README.md`.

Es la primera capacidad que nace despues del catalogo, asi que sirve de prueba
del invariante de ADR 0046: si anadirla obliga a editar la CLI o el MCP a mano,
el catalogo no cumplia lo que prometia.

Criterio de salida: conformance reproducible en verde; smoke en laboratorio;
`extended` ejerce la via de punta a punta con su RAG por subtarea (leccion de
ADR 0035: la capacidad se cierra cuando tiene consumidor real, no cuando
compila). En ese ejercicio, gate explicito: `degradations` vacio y
`params.effort` igual al que planifico. Si aparece
`requirements_unavailable`, la capa esta perdiendo campos y se ve ahi, no meses
despues.

### Fase v0.4-C: retirada de routing_rules

Ejecuta lo que ADR 0043 decidio y la linea del router dejo a medias: la clave
`routing_rules` sale del esquema, del cargador y del validador, con rechazo
tipado. Detalle, motivo y criterios de aceptacion en
[ficha v0.4/0001](fixes/v0.4/0001-retirada-de-routing-rules.md).

Va en esta linea porque romper contrato de config es MINOR y v0.4.0 ya se corta
como MINOR: aqui no cuesta version, y aplazarlo deja una clave que el validador
bendice y el motor ignora.

Criterio de salida: `config.validate` rechaza `routing_rules` con `ConfigError`
y mensaje accionable, por las tres interfaces; nada en `src/` la referencia;
digest de conformance intacto o recalculado y declarado.

## Linea del router semantico (abierta 2026-08-07; entregada en v0.3.0, con un pendiente)

Objetivo: el enrutado por dominio pasa de un filtro de palabras clave a un
clasificador semantico (ADR 0043). Un solo router para `domain.route` (publica)
y para las subtareas de `task.run`; `prompt.run` va directo (sin router);
`routing_rules.keywords` se retira; el core es agnostico en modelos. Version
objetivo: MINOR (rompe contrato de config); el numero lo corta el usuario. Misma
disciplina: contrato y bateria ANTES de implementar.

### Fase 1: contrato (completada 2026-08-07)

ADR 0043 reconciliado; `CORE_CONTRACT.md` actualizado (`domain.route` semantica,
`prompt.run` sin router, `task.run` sin dominio de nivel superior).

Criterio de salida (cumplido): decision reconciliada por el usuario y
registrada.

### Fase 2: config y bateria (completada 2026-08-10)

Esquema: `routing_rules.keywords`/`tags` fuera; `description` como entrada
normativa; objetivo `router` declarativo (modelo o dominio + perfil, en
conformance un fake guionizado); dominio por defecto designado EXPLICITAMENTE
(en vez del nombre magico `general`). Los dominios son config del operador; solo
el default es arquitectura (ADR 0043). Bateria congelada: `domain.route`
semantica con router fake; ruteo de subtareas de `task.run` por el router unico;
`prompt.run` sin declarar resuelve al dominio por defecto SIN router;
precedencia intacta; asignacion de modelo por dominio respetada. La plantilla
actualiza sus dominios de EJEMPLO con descripciones inequivocas (punto de
partida, no contrato).

Criterio de salida (cumplido): esquema (`router`, `default_domain` explicito) y
bateria (`eval/battery/router/domain_route.yaml`) congelados antes de tocar el
runtime.

### Fase 3: implementacion y paridad (completada 2026-08-10)

Router semantico con paridad CLI/REST/MCP; retirada de `_matches` y
`_resolve_domain_hint`; `prompt.run` directo; digest recalculado y declarado.

Entregada en tres pasadas, todas publicadas en v0.3.0: 3a (`domain.route`
semantica cuando hay `router` configurado), 3b-i (`prompt.run` sale del router y
`task.run` rutea cada subtarea) y 3b-ii (retirada del modo keyword: el router
semantico es el unico). Digest declarado en `eval/README.md`
(`6dcae1a5...`, 42 casos).

Criterio de salida (cumplido): conformance reproducible en verde; smoke en
laboratorio (enruta por sentido, no por palabras); core minimo instalable.

Pendiente de esta linea (no cerrada por la fase 3): `routing_rules` sigue en el
esquema (`config/schema.py`) y el validador aun comprueba la forma de
`keywords`/`tags`, aunque el runtime ya no los lee. Retirar una clave que el
motor ignora ROMPE configuraciones existentes (MINOR), asi que la forma de la
retirada -rechazo tipado o aviso- es decision pendiente, no olvido. Las
plantillas ya no la traen.

## Linea de presupuesto y esfuerzo de task.run (cerrada 2026-08-12)

Objetivo: dimensionar el presupuesto por el plan (ADR 0044) y permitir que el
consumidor elija un nivel de esfuerzo portable `low | medium | high` cuyos
limites declara el operador (ADR 0045). Impacto: MINOR; el numero lo corta el
usuario.

### Pasada 1: presupuesto dimensionado (completada)

`orchestration.token_budget` (`base`, `per_subtask`), concesion por pasada,
acumulacion y corte unico `max_total_tokens` implementados en el commit
`0bd7baf`. Los campos constantes anteriores quedan retirados.

### Pasada 2: niveles de esfuerzo (completada)

Entrada opcional `effort`, precedencia campo a campo sobre el bloque base
`medium`, `default_effort`, parametros efectivos y paridad CLI/REST/MCP. Los
ejes de maquina y la medicion del coste permanecen fuera del nivel. Bateria
integrada: 20/20; conformance total 81/81 con digest declarado en
`eval/README.md`; pytest verde con y sin extras.

## Fuera de este plan

- Implementar memoria, RAG, web, conciencia o agentes (repos externos).
- `capability.route` (clasificador consultivo de capacidad: propone
  atomica/iterativa/compleja sin ejecutar, ADR 0038): diferido hasta que
  exista un agente consumidor real (leccion MemoryPort).
- tool_contracts (invocacion de herramientas, ADR 0007): diferido hasta que
  exista una herramienta concreta que lo justifique (anti-entropia); sin fase
  asignada (ADR 0022).
- Optimizacion de rendimiento antes de tener el core funcionando.
