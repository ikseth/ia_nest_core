# Handoff de implementacion: fase 7 (interfaces MCP y REST minimas)

Destinatario: agente codificador (Codex/Sonnet).
Autor: Claude Code (Opus), rol disenador.
Verificacion: Opus.
Base: `main` con fases 6a y 6b integradas y verificadas.

Autocontenido pero NO sustituye a los documentos. Lee `CORE_CONTRACT.md`,
`ARCHITECTURE.md`, los ADRs citados y el codigo de 6a/6b en
`src/ianest_core/` (reutilizalo).

## Objetivo

Exponer las capacidades del core por MCP y REST con paridad EXACTA a la CLI
(sin logica distinta, regla de `CORE_CONTRACT.md`). La CLI de 6a/6b es la
referencia de comportamiento.

## Dentro de fase 7

1. Capa de servicio compartida (paridad por construccion): extrae un modulo
   `service` con una funcion por capacidad: `run_prompt`, `route_domain`,
   `list_models`, `list_domains`, `validate_config`, `run_eval`, `health`.
   Reciben datos simples y devuelven dicts/streams. CLI, MCP y REST llaman
   SOLO a esta capa; ninguna interfaz contiene logica de negocio. Refactoriza
   la CLI para que use esta capa (hoy llama a los runtimes directamente).
2. `runtime.health` (CORE_CONTRACT): nueva capacidad. Comprueba proceso core,
   disponibilidad de backend/modelos (reutiliza `AvailabilityProvider` de
   6b), deteccion GPU/runtime cuando aplique (best-effort; el backend es
   remoto, asi que limitado), y declara la version de protocolo MCP
   (ADR 0006). Devuelve estado estructurado.
3. Interfaz MCP: usa el SDK oficial `mcp` (ADR 0009). Expone las capacidades
   como herramientas MCP con salida estructurada. Declara y hace verificable
   la version de protocolo (ADR 0006) via `runtime.health`.
4. Interfaz REST: Starlette + uvicorn (ADR 0021). Endpoints por capacidad.
   Streaming SSE para `prompt.run` en modo streaming (ADR 0004/D2); el modo
   bloqueante colecta. Sin logica de negocio.

## No reinventar (ya fijado)

- Paridad y "sin logica distinta a la CLI" (CORE_CONTRACT).
- Streaming como primitiva (ADR 0004): REST via SSE, MCP streaming donde
  aplique; bloqueante colecta.
- Errores (ADR 0020): misma serializacion `{type, message, field}` en las
  tres interfaces.
- SDK oficial MCP y Starlette (ADR 0009 / 0021).

## Decision a cerrar (reportar, no inferir en silencio)

La version exacta del protocolo MCP (ADR 0006): usa la que implementa el SDK
oficial, declarala en `runtime.health` y REPORTAME cual es para finalizar el
ADR 0006. Si el SDK ofrece varias, PARA y pregunta.

## Fuera de fase 7 (NO implementar)

- `reasoning_loop` / `reasoning.run`, `tool_contracts` -> fases posteriores.
- Memoria real, RAG, agentes -> repos externos.

## Blanco de aceptacion

- Un cliente MCP externo ejecuta `prompt.run` con paridad a la CLI (misma
  estructura de respuesta).
- Un cliente REST ejecuta `prompt.run` (bloqueante y SSE) con paridad a la
  CLI.
- `runtime.health` responde por CLI/MCP/REST, declara la version MCP y es
  verificable.
- Las tres interfaces comparten la capa de servicio; la logica vive en
  `src/ianest_core`, no en las capas de interfaz (revisable).
- `pytest` en verde, con tests de paridad (misma entrada por la capa de
  servicio -> misma salida) y de `runtime.health`.
- Dependencias nuevas (`mcp`, `starlette`, `uvicorn`) como extra opcional en
  `pyproject.toml`; el core basico sigue instalable sin ellas.

## Restricciones y convenciones

- Python 3.13; pip + venv; pytest. Identificadores/claves en ingles
  snake_case; prosa en espanol sin tildes. Modulos pequenos; reutiliza 6a/6b.
- Repo PUBLICO: nada interno en archivos versionados; endpoints/secretos por
  env var. Corres en esta maquina: puedes leer `local/`; NO conectes al host
  de laboratorio; usa fakes para los tests.
- Ambiguedad o contradiccion en los docs -> PARA y preguntame.

## Entrega y handoff de vuelta

Rama nueva desde `main` (p.ej. `fase-7-mcp-rest`), tests en verde, y una nota
con las decisiones tomadas y la version MCP declarada. Opus verifica paridad
CLI/REST/MCP y `runtime.health`.
