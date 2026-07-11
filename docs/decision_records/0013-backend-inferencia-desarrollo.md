# Decision 0013: backend de inferencia de desarrollo

Fecha: 2026-07-10

## Decision

El backend de modelos para desarrollo y pruebas corre en un host remoto con
GPU, y el core lo consume via el adaptador OpenAI-compatible (ADR 0003). El
core NO fija el host: la direccion concreta se resuelve por variable de
entorno / config local no versionada.

- Endpoint configurable via `OPENAI_COMPAT_BASE_URL` (o en la seccion
  `models[].endpoint` de la config, ADR 0014).
- Caracteristicas requeridas del host (no su identidad): GPU CUDA de ~12 GB
  de VRAM (suficiente para un modelo 7-8B cuantizado), CPU multinucleo y RAM
  amplia.
- La identidad concreta del host de laboratorio (IP, acceso, specs exactas)
  vive en `local/` (no versionado) y en `.env` (ver `.env.example`), no en el
  repo.

Backend software y modelo (propuesta, ajustable al instalar): Ollama sobre la
GPU (expone endpoint OpenAI-compatible, gestion de modelos simple), con un
modelo 7-8B cuantizado (por ejemplo Llama 3.1 8B o Qwen2.5 7B).

## Motivo

La maquina de trabajo no tiene GPU ni backend; un host de laboratorio con GPU
si es adecuado para el smoke de calidad de la fase 6a. El adaptador
OpenAI-compatible desacopla el core del backend, y la indireccion por env
var/config mantiene el repo limpio de detalles de red concretos.

## Consecuencia

- Precondicion del smoke de calidad: la GPU del host debe estar sana antes de
  ejecutarlo (comprobable via `runtime.health` / deteccion GPU). Si la GPU no
  esta disponible, el smoke no corre; la pista de conformance (adaptadores
  fake) no se ve afectada y sigue reproducible sin red ni GPU.
- Credenciales y direcciones concretas nunca se versionan (ver `.env.example`
  y `local/`).
- El endpoint y el modelo son configuracion (ADR 0014), no codigo.
