# Changelog

Formato basado en Keep a Changelog; versionado segun `docs/VERSIONADO.md`
(ADR 0030). Sin acentos por convencion del repo.

## [No publicado]

### Cambiado
- Doctrina de fronteras: RAG, memoria y datos web se conectan por enriquecimiento
  (solo lectura), no por `tool_contracts` (ADR 0031). `tool_contracts` queda
  acotado a integraciones que actuan.
- Registro de capas y politica de dependencias entre capas: cada capa versiona su
  contrato y fija las versiones de las que depende; el core hospeda el indice
  (ADR 0032, `docs/FRONTERAS.md`).
- Nuevas capas en el mapa de repos: `ia_nest_web` (GUI) y `ia_nest_core_ops`
  (monitorizacion), separadas de enriquecimiento y de control/verificacion.

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

[No publicado]: https://github.com/ikseth/ia_nest_core/compare/v0.1.0...HEAD
[v0.1.0]: https://github.com/ikseth/ia_nest_core/releases/tag/v0.1.0
