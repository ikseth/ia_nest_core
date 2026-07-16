# IA_NEST Core Context

Estado: validado
Version: 0.3 - 2026-07-16
Revisado por: Claude Code y Codex, en colaboracion con el usuario

## Mision

Construir el core basico de IA_NEST: un nucleo IA local que gestione modelos,
dominios, orquestacion, runtime local e interfaz MCP.

## Principios

1. Core primero, modulos despues.
2. Configuracion declarativa antes que logica implicita.
3. Contratos pequenos, versionados y testeables.
4. Una capacidad nueva no entra al core si puede ser una herramienta externa.
5. Todo cambio debe preservar trazabilidad y evaluacion reproducible.
6. Filosofia UNIX: piezas pequenas, componibles y verificables.
7. Nombres, atributos y funciones deben seguir convenciones normalizadas
   (ver `docs/CONVENCIONES.md`).

Criterio para el principio 4 (nucleo vs herramienta externa): si una
capacidad necesita acceso al estado interno del registry o del router para
funcionar, es core; si no, es herramienta externa.

## No objetivos actuales

- No integrar Home Assistant directamente.
- No implementar RAG.
- No implementar busqueda web.
- No crear frontend administrativo completo.
- No implementar agentes autonomos.
- No crear memoria autobiografica ni consciencia.
- No crear peers ni red distribuida.
- No incluir automatizacion Linux destructiva.
- No migrar codigo de IA_NEST sin revision.

## Core cerrado significa

Cada punto se considera cumplido cuando la capacidad correspondiente de
`docs/CORE_CONTRACT.md` pasa su prueba de aceptacion.

- Registry de modelos funcional (`model.list`).
- Router de dominios funcional (`domain.list`, `domain.route`).
- Runtime de inferencia local funcional (`prompt.run`).
- Interfaz MCP basica funcional (interfaces publicas de `CORE_CONTRACT.md`).
- Bucle de razonamiento limitado y observable (`reasoning.run`).
- Evaluacion reproducible por bateria de prompts (`eval.run`).
- Trazabilidad por request (campo trazabilidad de `prompt.run`/`reasoning.run`).
- Configuracion declarativa (`config.validate`).
- Scripts de instalacion y deteccion de runtime/GPU (`runtime.health`).
- Tests de aceptacion basicos (reglas de compatibilidad de `CORE_CONTRACT.md`).

## Metodo de trabajo

- Usar steelman en analisis y propuestas relevantes.
- Preguntar antes de inferir decisiones criticas o de alto impacto.
- Mantener documentos pequenos y normativos.
- Registrar decisiones estructurales en `docs/decision_records/`.
- Registrar correcciones y mejoras pequenas en `docs/fixes/`, segun
  `docs/VERSIONADO.md`; reservar los ADR para decisiones estructurales.
- Incluir cabecera humana/IA en scripts no triviales.

## Colaboracion entre varias IA

Este repo puede recibir propuestas de mas de una IA (por ejemplo Codex y
Claude) de forma independiente.

- Modo por defecto: modo ciego. Cada IA propone sobre el mismo estado de
  documentos, sin ver la propuesta de la otra.
- Ninguna propuesta estructural se aplica directamente. Se reconcilia por
  el usuario y solo el resultado reconciliado se registra como ADR.
- Si una IA detecta una inconsistencia entre documentos, no debe asumir que
  es un error propio: puede ser trabajo en curso de otra IA. Debe
  senalarla, no corregirla por inferencia.

## Regla anti-entropia

Ningun modulo nuevo se acepta por utilidad potencial.

Solo se acepta si:

- pertenece al alcance actual,
- tiene contrato escrito,
- tiene prueba de aceptacion,
- no duplica una capacidad que pueda vivir fuera del core.

## Mapa de repos previsto

- `ia_nest_core`: core basico.
- `ia_nest_core_extended`: enriquecimiento de contexto (RAG, memoria, datos web).
- `ia_nest_web`: GUI web (interfaz de gestion y de usuario).
- `ia_nest_core_conscience`: control/verificacion (memoria sobre los modelos).
- `ia_nest_core_ops`: monitorizacion/ops (estado en vivo y alertas).
- `ia_nest_module_*`: modulos propios.
- `ia_nest_external_*`: integraciones que actuan sobre apps externas (tool_contracts).
- `ia_nest_agents` o `ia_nest_agent_*`: agentes que usan IA_NEST.

Enriquecimiento vs herramientas: RAG, memoria y datos web ENRIQUECEN el prompt
(solo lectura, costura tipo Port); las integraciones que ACTUAN usan
`tool_contracts` (ADR 0007). Son costuras distintas (ADR 0031). Dependencias
entre capas: cada capa versiona su contrato y fija las versiones de las que
depende; el core solo hospeda el indice (ADR 0032, `docs/FRONTERAS.md`).
