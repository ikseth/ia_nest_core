# Decision 0021: framework REST (Starlette)

Fecha: 2026-07-11

## Decision

La interfaz REST (fase 7) usa Starlette + uvicorn (ASGI). El streaming de
`prompt.run` se expone por SSE (ADR 0004).

## Motivo

Adopta un estandar (ADR 0009) con SSE nativo y pocas dependencias, sin el
peso de FastAPI/pydantic (redundante con nuestros dataclasses y
`config.validate` propios). Coherente con el ethos minimalista del proyecto.

## Consecuencia

- Nuevas dependencias: `starlette`, `uvicorn`, declaradas como extra opcional
  en `pyproject.toml` (p.ej. `[project.optional-dependencies] api`); el core
  basico sigue instalable sin ellas.
- La capa REST es fina: sin logica de negocio, llama a la misma capa de
  nucleo que la CLI (paridad, CORE_CONTRACT).
- MCP usa el SDK oficial (ADR 0009); su version de protocolo se declara en
  `runtime.health` y cierra el ADR 0006 al implementar.
