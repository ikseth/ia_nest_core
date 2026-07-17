# Changelog

Formato basado en Keep a Changelog; versionado segun `docs/VERSIONADO.md`
(ADR 0030). Sin acentos por convencion del repo.

## [No publicado]

### Anadido
- `finish_reason` crudo del backend en el evento `done`, la traza y telemetria
  JSONL de `prompt.run`, los registros de subtarea de `task.run` y los pasos de
  `reasoning.run`; fakes deterministas con `stop` por defecto y valor
  scriptable ([ficha 0002](docs/fixes/v0.2/0002-finish-reason.md)). Impacto:
  patch.

### Cambiado
- Doctrina del ente: dos funciones nerviosas (ADR 0037). `ia_nest_core_ops`
  se reconcilia como `ia_nest_core_pulse` -sistema nervioso autonomo: observa
  la telemetria de todos y regula parametros tecnicos dentro de los techos del
  core, subordinado a conscience-, y pasa al pack basico del ente. conscience
  queda como sistema nervioso voluntario (puro, psicologico). Frontera con la
  GUI (presentacion) y prerrequisito `finish_reason` en el core registrados.

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
