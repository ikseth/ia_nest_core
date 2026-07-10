# Decision 0003: protocolo de cable del runtime OpenAI-compatible

Fecha: 2026-07-10

## Decision

`prompt_runtime` no habla con los backends directamente: habla con una
interfaz `ModelAdapter`. El adaptador por defecto usa el dialecto
OpenAI-compatible (Chat Completions).

## Motivo

Ollama, llama.cpp (server) y vLLM ya exponen ese dialecto. Maximiza la
prioridad "facilidad de cambio de modelos" de `VISION_FUNCIONAL.md` sin
acoplar el core a un proveedor concreto.

## Consecuencia

Un backend nuevo se soporta escribiendo un adaptador, no tocando el runtime.
Los parametros de sampling propios de un backend que no cubre el dialecto
comun se pasan como `extra` opaco. Detalle en `ARCHITECTURE.md` (D1).
