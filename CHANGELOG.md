# Changelog

Formato basado en Keep a Changelog; versionado segun `docs/VERSIONADO.md`
(ADR 0030). Sin acentos por convencion del repo.

## [No publicado]

### Anadido
- Contrato de la GPU del backend en `runtime.health` (ADR 0049): dos campos con
  dos significados que no se mezclan. `gpu` sigue describiendo el runtime LOCAL
  -en una maquina sin GPU, `available: false` es cierto y no es regresion- y
  `backend.gpu` declara lo que el backend dice de su propio uso de GPU
  (`in_use | cpu_only | unknown`, con `models_loaded`). `cpu_only` es el que
  justifica el campo: un modelo que no cabe en memoria de video no falla, cae a
  CPU en silencio y responde mucho mas lento. La sonda es especifica del
  proveedor y opcional, por la costura del provisioning (ADR 0029), y
  `runtime.health` nunca falla por ella. Implementacion en la linea de
  observacion del backend del PLAN. Impacto: adicion compatible (patch).

### Anadido
- Contrato del catalogo unico de capacidades (ADR 0046, cierra
  `extended CR-0002`): un catalogo declarativo pasa a ser la fuente de la que se
  derivan la CLI y las rutas REST y contra la que se asertan las herramientas
  MCP, en lugar del mismo dato escrito por triplicado. Nueva capacidad
  `capability.list` con paridad CLI/REST/MCP -nombre, parametros y proyeccion
  por interfaz de cada capacidad, con los huecos declarados-, `core_version` en
  `capability.list` y en `runtime.health`. Entregado: la CLI y la tabla de rutas
  REST se construyen recorriendo el catalogo, y un gate bidireccional aserta que
  las herramientas MCP no se desvian de el. Impacto: adicion compatible (patch
  por politica; se publica dentro de v0.4.0).
- Contrato del plan explicito de `task.run` (ADR 0040, enmendado por ADR 0047;
  cierra `extended CR-0001`): capacidad `task.plan`, entrada opcional `plan` en
  `task.run`, corte tipado `replan_unavailable` y campo `plan_source` en
  `plan_ready`. ADR 0047 fija lo que ADR 0040 no podia prever por ser anterior a
  ADR 0041, 0044 y 0045: el plan suministrado hereda su `effort` salvo que la
  peticion declare otro, concede presupuesto como cualquier plan, transporta sus
  `requirements` -y si no los trae, el core lo declara como degradacion
  `requirements_unavailable` en vez de afirmar una cobertura que nadie
  comprobo-, y `plan_attempts` vale 0 porque cuenta derivaciones del
  planificador. Alcance `mode=pipeline`. Implementacion en las fases v0.4-B2/B3
  del PLAN. Impacto: adicion compatible (patch por politica; se publica dentro
  de v0.4.0).

### Cambiado
- `task.run` pasa a devolver JSON en `POST /task/run` y su flujo SSE se muda a
  la capacidad nueva `task.stream` -> `POST /task/stream` (ADR 0046, enmienda
  D5-a). Motivo: las capas de encima derivan la ruta del NOMBRE de la capacidad
  sin tabla intermedia, asi que `X.run` tiene que significar lo mismo en las
  tres familias; hasta v0.3, `/task/run` era SSE mientras `/prompt/run` y
  `/reasoning/run` eran JSON. Con esto la bandera `streaming` del catalogo pasa
  de informativa a operativa para un reenviador generico. **Rompe** a quien haga
  POST a `/task/run` esperando eventos: debe pasar a `/task/stream`. Avisado a
  `ia_nest_extended` por el canal de CR antes de que suba su pin. Impacto:
  **minor**.
- `tags` se retira de `domain.route` en REST y en MCP. Estaba muerto desde
  ADR 0043 -era del filtro de palabras clave, y `DomainRouter.route` lo
  descartaba con un `del tags` en su primera linea- pero seguia viajando por dos
  de las tres interfaces, mientras la CLI nunca lo expuso. Lo saco a la luz el
  gate del catalogo (ADR 0046) al exigir que los parametros declarados coincidan
  con las tres interfaces. Un cliente REST que lo siga enviando no recibe error;
  la herramienta MCP si cambia de esquema, y por eso el impacto es minor
  ([ficha v0.4/0002](docs/fixes/v0.4/0002-retirada-de-tags-de-domain-route.md)).
  Impacto: **minor**.
- `routing_rules` se retira del esquema de configuracion, ejecutando lo que
  ADR 0043 decidio y la linea del router dejo tolerado: la clave sale de
  `DomainConfig`, del cargador y del validador, y una config que la traiga falla
  con `ConfigError` (`field=routing_rules`) y un mensaje que nombra la
  alternativa (`router` mas la `description` de cada dominio). Se hace en esta
  linea porque romper contrato de config es minor y v0.4.0 ya lo es.
  Implementacion en la fase v0.4-C del PLAN
  ([ficha v0.4/0001](docs/fixes/v0.4/0001-retirada-de-routing-rules.md)).
  Impacto: **minor**.

### Corregido
- Ayuda de la CLI alineada con ADR 0043: los epilogos de `prompt run/stream` y
  `reasoning run/stream` afirmaban que sin `--model` ni `--domain` "se usa el
  router". No es asi desde la fase 3b-i: se resuelve el dominio por defecto SIN
  enrutar. Solo texto de ayuda; sin cambio de comportamiento. Impacto: patch.
- Registro alineado con el codigo publicado, sin cambio de producto: la entrada
  del router semantico de v0.3.0 recoge tambien la fase 3b-ii (retirada del modo
  keyword), que se publico en esa version y no estaba anotada; `docs/PLAN.md`
  marca las fases 2 y 3 de esa linea como completadas y deja anotado lo que
  queda (`routing_rules` sigue en el esquema como clave ignorada);
  `docs/VERSIONADO.md` deja de enumerar un subconjunto de capacidades como
  contrato publico (omitia `task.run`) y remite a `CORE_CONTRACT.md`;
  `CORE_CONTRACT.md` retira de `task.run` el rotulo "implementacion en curso".

## [v0.3.0] - 2026-08-12

### Anadido
- Niveles de esfuerzo de `task.run` (ADR 0045): entrada opcional
  `effort=low|medium|high`, config aditiva `orchestration.effort` y
  `orchestration.default_effort`, resolucion campo a campo y nivel efectivo en
  `params`, con paridad CLI/REST/MCP. Los niveles gobiernan solo ejes de
  intencion; no alteran ejes de maquina ni `token_budget`. Impacto: **minor**.
- Implementacion de la etapa PLAN de los invariantes I1, I2 e I4 de
  `task.run` (ADR 0041) en `pipeline` y `coverage`: requisitos y cobertura
  declarada por unidad, una sola renegociacion compartida, tolerancia de
  envoltorios sin perdida, degradacion declarada a una subtarea y contadores
  aditivos. La etapa EVALUATE gana su renegociacion independiente y, si la
  decision sigue ilegible, conserva la respuesta asumiendo `done` con
  degradacion declarada. `plan_ready` cuenta planes derivados y no se repite en
  `rerun`. Bateria integrada: 19 casos nuevos, conformance 61/61 y digest
  declarado en `eval/README.md`. Impacto: patch.
- Contrato: el enrutado por dominio pasa a ser SEMANTICO (ADR 0043). Un
  clasificador por sentido reemplaza el filtro de palabras clave (cuya confianza
  estaba falseada); un solo router para `domain.route` (que se conserva publica)
  y para las subtareas de `task.run`. `prompt.run` va DIRECTO: sin router, al
  dominio declarado o al por defecto (enmienda el punto 3 de ADR 0019).
  `task.run` no recibe dominio de nivel superior. `routing_rules.keywords` se
  retira; la `description` de cada dominio pasa a ser la entrada del router. Los
  dominios son config del operador; solo el dominio por defecto es arquitectura
  (se designa explicito). El core es agnostico en modelos. Contrato fijado
  (fase 1); config, bateria e implementacion en la linea del router
  (`docs/PLAN.md`). Impacto: minor (rompe contrato de config).
- Contrato del modo de cobertura de `task.run` (`mode=coverage`: unidades
  verificables, ledger, validacion separada, eventos `answer_chunk` y
  `coverage_updated`, cortes `max_chunks | max_total_tokens | no_progress`)
  y seccion de seleccion de capacidad en `CORE_CONTRACT.md` (ADR 0038);
  implementacion en fases v0.3-1/2/3 del PLAN. Impacto: minor (version
  objetivo v0.3.0).
- Implementacion completa del modo coverage (fases v0.3-1/2/3): config
  `orchestration.coverage`, bateria v0.3 congelada e integrada
  (conformance 34/34, digest recalculado y declarado, ADR 0017), runtime
  con ledger y salida progresiva, paridad CLI/REST/MCP (`--mode`), manual,
  y smoke de laboratorio dentro de umbral con robustecimiento
  ([ficha v0.3/0001](docs/fixes/v0.3/0001-derive-coverage-tolerante.md)).
  Parte de v0.3.0.
- `finish_reason` crudo del backend en el evento `done`, la traza y telemetria
  JSONL de `prompt.run`, los registros de subtarea de `task.run` y los pasos de
  `reasoning.run`; fakes deterministas con `stop` por defecto y valor
  scriptable ([ficha 0002](docs/fixes/v0.2/0002-finish-reason.md)). Impacto:
  patch.

### Cambiado
- El presupuesto de tokens de `task.run` lo dimensiona el plan (ADR 0044):
  `orchestration.token_budget` (`base`, `per_subtask`) sustituye al techo
  constante, la concesion es `base + per_subtask * n` por pasada -con el factor
  `(1 + max_retries_per_unit)` en `coverage`- y se acumula. El presupuesto
  decide si empieza otra pasada y nunca mutila la que esta en curso. El corte
  tipado pasa a ser `max_total_tokens`, unico para los dos modos;
  `orchestration.max_context_tokens` y `coverage.max_total_tokens` quedan
  retirados y se ignoran. `reasoning.run` conserva su `max_context_tokens` de
  perfil, que es otro concepto (ADR 0008). Defaults calibrados en laboratorio:
  `base: 2000`, `per_subtask: 3000`. Impacto: **minor** (desaparece un corte
  tipado del contrato y se retiran campos del esquema).

- Router semantico, fases 3a, 3b-i y 3b-ii (ADR 0043): `domain.route` clasifica
  por sentido con el `router` declarado; `prompt.run` sin modelo ni dominio
  resuelve directamente el dominio por defecto, sin router; `task.run` enruta de
  forma explicita cada subtarea que no tenga `domain` ni un `domain_hint`
  resoluble; y el modo keyword queda RETIRADO (el router semantico es el unico:
  sin `router` en la config, enrutar es `RoutingError`). Conformance 42/42 y
  digest recalculado. `routing_rules` sobrevive en el esquema como clave
  ignorada; su retirada queda pendiente (`docs/PLAN.md`). Impacto: minor, como
  parte del cambio de contrato de config ya declarado por ADR 0043.
- Salida de la CLI: stdout lleva solo la respuesta, el progreso va a stderr
  como linea concisa, `--json` intacto y nueva bandera `--quiet`; uniforme en
  `prompt.run`, `reasoning.run` y `task.run` (ADR 0039). Impacto: patch.
- Doctrina del ente: dos funciones nerviosas (ADR 0037). `ia_nest_core_ops`
  se reconcilia como `ia_nest_core_pulse` -sistema nervioso autonomo: observa
  la telemetria de todos y regula parametros tecnicos dentro de los techos del
  core, subordinado a conscience-, y pasa al pack basico del ente. conscience
  queda como sistema nervioso voluntario (puro, psicologico). Frontera con la
  GUI (presentacion) y prerrequisito `finish_reason` en el core registrados.
- Gobernanza: nace `ia_nest_meta`, repo de gobernanza del ente (el taller, fuera
  del mapa ente/exterior de ADR 0033). Se re-hogan alli las convenciones
  transversales (origen ADR 0016) y la doctrina multi-IA (origen
  `IA_NEST_CORE_CONTEXT.md`); este repo conserva punteros y ADR 0016 conserva su
  cuerpo con una seccion `Estado posterior`. Ver meta ADR 0001 y meta ADR 0002.
  Impacto: ninguno (no toca contrato publico).
- Gobernanza: el registro de capas y su grafo de dependencias pasan a
  `ia_nest_meta/docs/REGISTRO_CAPAS.md` (meta ADR 0003), con los datos
  corregidos y una regla de mantenimiento. `docs/FRONTERAS.md` conserva la
  costura que el core expone a cada capa y marca `[doctrina de capa]` el diseno
  interno de capas aun no sembradas. ADR 0032 conserva su cuerpo con una seccion
  `Estado posterior`. `docs/VERSIONADO.md` anade al proceso de publicacion la
  actualizacion de la fila propia en el registro. Impacto: ninguno.
- Gobernanza: la politica de SemVer (esquema, que numero subir, proceso de
  publicacion) pasa a `ia_nest_meta/docs/POLITICA_SEMVER.md` (meta ADR 0004).
  `docs/VERSIONADO.md` conserva lo unico que solo el core fija: que cuenta como
  su contrato publico y su registro de fichas. `docs/CAPAS_FUTURAS.md` queda
  como backlog del motor: el registro de repos va al registro de capas y los
  concerns del ente sin repo asignado, a meta. ADR 0030 conserva su cuerpo con
  una seccion `Estado posterior`. Impacto: ninguno.
- Contrato: `extended CR-0001` (enriquecimiento por subtarea en `task.run`)
  resuelto como REFORMULADO (ADR 0040). Se acepta la necesidad y se separa en
  dos mitades: que dominio le toca a cada subtarea solo lo produce el core, y
  meterle el conocimiento es de la capa (ADR 0031, via 2). Se descarta la forma
  sugerida -un checkpoint con valor de vuelta-: los checkpoints del core son de
  una sola direccion, el punto de insercion cae dentro del pool de hilos del
  fan-out, y el consumidor real habla por REST, con lo que un puerto en proceso
  le es inalcanzable y una llamada saliente invertiria el grafo de dependencias.
  En su lugar, granularidad de la entrada: capacidad `task.plan` (devuelve el
  plan con el dominio ya resuelto, sin ejecutarlo) y entrada opcional `plan` en
  `task.run`, con corte tipado `replan_unavailable` y campo `plan_source` en
  `plan_ready`. La capa enriquece entre las dos llamadas; el core no abre
  ninguna costura hacia arriba. Un bus bidireccional generico queda descartado
  hoy y NO cerrado: los anclajes del VETO diferido (ADR 0036) siguen en pie.
  Contrato fijado; implementacion en la linea siguiente (`docs/PLAN.md`).
  Impacto cuando se entregue: minor.

### Corregido
- Salida `--verbose` de la CLI: cada linea de progreso en stderr lleva el
  tiempo acumulado desde el primer evento (`[  0.0s]`); el render de coverage
  deja de mostrar `iteration` y `decision` inexistentes como `None`, sin
  alterar pipeline, stdout, JSON, runtime ni telemetria
  ([ficha v0.3/0013](docs/fixes/v0.3/0013-verbose-sin-campos-fantasma-y-con-reloj.md)).
  Impacto: patch.
- En modo pipeline, cada subtarea recibe el objetivo global solo como contexto
  y conserva su enunciado como unico contenido a producir; el enrutado y el
  registro mantienen el enunciado pelado. COMBINE ahora estructura resultados
  divergentes sin juzgar su exactitud ni introducir matices sin divergencia
  ([ficha v0.3/0012](docs/fixes/v0.3/0012-subtareas-con-contexto-y-combinado-coherente.md)).
  Impacto: patch.
- En modo pipeline, `depends_on` declara y tolera indices enteros base 0: se
  aceptan enteros y cadenas de digitos, se rechazan booleanos y formas
  invalidas, y los indices fuera de rango se distinguen de los ciclos antes del
  fan-out ([ficha v0.3/0011](docs/fixes/v0.3/0011-dependencias-de-pipeline-tolerantes.md)).
  Impacto: patch.
- En modo pipeline, una decision `done` de `task.run` prevalece sobre los
  limites de contexto y tiempo alcanzados al completar esa pasada; el
  presupuesto por defecto de orquestacion pasa a `16384`
  ([ficha v0.3/0010](docs/fixes/v0.3/0010-presupuesto-puente-y-merito-sobre-techo.md)).
  Impacto: patch.
- Los cortes por `max_context_tokens` de `task.run` evaluan el acumulado
  real de tokens de todas las llamadas (antes solo el override
  `simulated`, inoperante con backend real); el acumulado queda expuesto
  en la traza ([ficha 0003](docs/fixes/v0.2/0003-contabilidad-tokens-task-run.md)).
  Impacto: patch.
- Modo coverage robustecido tras el smoke real: el validador devuelve solo
  ids y el parser tolera varios formatos de salida
  ([ficha v0.3/0002](docs/fixes/v0.3/0002-parser-cobertura-tolerante.md)); el
  generador emite solo el contenido de sus unidades, sin preambulo ni cierre
  ([ficha v0.3/0003](docs/fixes/v0.3/0003-generador-coverage-sin-boilerplate.md)).
  Impacto: patch.

## [v0.2.0] - 2026-07-16

Orquestacion multi-modelo (linea v0.2 del PLAN, fases v0.2-0 a v0.2-3) y
doctrina del ente. Validado en laboratorio: conformance 23/23 con digest
declarado y smoke 3/3 con modelos reales. Quiesce (fase v0.2-4) diferido hasta
sembrar conscience.

### Anadido
- Implementacion de `task.run`: orquestacion PLAN/ROUTE/FAN-OUT/COMBINE/EVALUATE,
  checkpoints observables, limites tipados, telemetria enlazada por subtarea y
  paridad CLI/REST(SSE)/MCP (ADR 0036). Impacto: minor; objetivo: v0.2.0.
- Contrato de `task.run` (orquestacion multi-modelo con checkpoints observables
  y cortes tipados) fijado en `CORE_CONTRACT.md` (ADR 0036); implementacion en
  fases v0.2-2/3. Impacto: minor (version objetivo v0.2.0).
- Ayuda CLI jerarquica y descriptiva para todos los grupos, acciones y opciones
  de `ianest` ([ficha 0001](docs/fixes/v0.1/0001-ayuda-cli-jerarquica.md)).
- Bateria de evaluacion v0.2: 13 casos conformance (incl. enmienda
  `task_subtask_unknown_hint`: domain_hint consultivo) + 2 smoke; digest
  declarado `1d405c95...`. Robustecimientos surgidos del smoke real: parseo
  tolerante de plan/decision y hint de dominio consultivo con
  `domain_hint_ignored` en el arbol.

### Cambiado
- Retirada la costura interna de memoria (`MemoryPort`, adaptador nulo y lectura
  de contexto); `ia_nest_core_extended` asume estrategia y ejecucion, mientras
  el core conserva la identidad de segmentacion como clave (ADR 0035). Impacto:
  patch.
- Doctrina de fronteras: RAG, memoria y datos web se conectan por enriquecimiento
  (solo lectura), no por `tool_contracts` (ADR 0031). `tool_contracts` queda
  acotado a integraciones que actuan.
- Registro de capas y politica de dependencias entre capas: cada capa versiona su
  contrato y fija las versiones de las que depende; el core hospeda el indice
  (ADR 0032, `docs/FRONTERAS.md`).
- Nuevas capas en el mapa de repos: `ia_nest_web` (GUI) y `ia_nest_core_ops`
  (monitorizacion), separadas de enriquecimiento y de control/verificacion.
- Doctrina de identidad: el ente IA_NEST = core + extended + conscience + GUI;
  el exterior (agents, external, ops, otras entidades) consume contratos
  (ADR 0033). Orquestacion multi-modelo como linea v0.2 del core y conscience
  como supervisor dual live/sueno que sedimenta comportamiento (ADR 0034).
  Enriquecimiento decidido en la capa (via 2, `docs/FRONTERAS.md`).

## [v0.1.0] - 2026-07-15

Primer cierre del core: completo (fases 1-10 de `docs/PLAN.md`) y validado en
laboratorio sobre hardware real (RTX 3060 + Ollama).

### Anadido
- Core de orquestacion local backend-agnostico (HTTP OpenAI-compatible por
  endpoint via env var).
- Capacidades: `prompt.run`, `reasoning.run` (bucle de razonamiento controlado),
  `domain.route` (ruteo por dominio con reglas declarativas), `eval.run`
  (conformance determinista + smoke), `runtime.health`/deteccion de runtime-GPU.
- Registro de modelos, politica de fallo (preferido -> alternativos -> error
  tipado), resolucion de precedencia modelo/dominio/router.
- Adaptador de modelo streaming-first (eventos token/step/trace/done/error) y
  adaptador fake para conformance.
- Configuracion declarativa YAML con perfiles (muestreo, limites de
  razonamiento, `system` prompt, `extra` opaco).
- Telemetria CSV+JSONL con rotacion (best-effort) y taxonomia de error
  `CoreError`.
- Costura de memoria (`MemoryPort` + `NullMemoryAdapter`).
- Interfaces CLI (`ianest`), REST (Starlette+SSE) y MCP (SDK oficial, stdio+SSE)
  con paridad via capa de servicio compartida.
- Provisioning opcional de modelos: `ianest model pull` con `OllamaProvisioner`
  (ADR 0029).
- Instalacion: `install.sh` (venv, interfaces, `--service` systemd),
  `deploy/setup.sh` (desde cero con Ollama en Docker), `ianest init`.
- Manual de usuario modular (`docs/manual/`), fronteras hacia capas externas
  (`docs/FRONTERAS.md`) y 30 ADRs.

[No publicado]: https://github.com/ikseth/ia_nest_core/compare/v0.2.0...HEAD
[v0.2.0]: https://github.com/ikseth/ia_nest_core/compare/v0.1.0...v0.2.0
[v0.1.0]: https://github.com/ikseth/ia_nest_core/releases/tag/v0.1.0
