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

## Fase 10: Plan de repos/modulos externos (actual)

Objetivo: documentar las fronteras de handoff hacia los repos externos:
`MemoryPort` -> `ia_nest_core_extended`; conciencia ->
`ia_nest_core_conscience`; integraciones -> `ia_nest_external_*`; agentes ->
`ia_nest_agents`.

Criterio de salida:
- Contratos de frontera documentados y versionados.
- Checklist "Core cerrado significa" de `IA_NEST_CORE_CONTEXT.md` cumplido.

## Fuera de este plan

- Implementar memoria, RAG, web, conciencia o agentes (repos externos).
- tool_contracts (invocacion de herramientas, ADR 0007): diferido hasta que
  exista una herramienta concreta que lo justifique (anti-entropia); sin fase
  asignada (ADR 0022).
- Optimizacion de rendimiento antes de tener el core funcionando.
