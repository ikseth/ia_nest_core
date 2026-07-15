# Decision 0028: estrategia de recursos (backend, GPU) y readiness del core

Fecha: 2026-07-15

## Decision

- El core es **agnostico al backend**: habla HTTP OpenAI-compatible a un
  endpoint (`OPENAI_COMPAT_BASE_URL`). Soporta el backend (Ollama u otro) en el
  host, en Docker o en remoto. No sabe ni gestiona Docker/GPU.
- **Backend recomendado**: Ollama en **Docker con GPU** (NVIDIA Container
  Toolkit + reserva de GPU en compose), como servicio (`restart:
  unless-stopped`). Compartimentado (preferencia del proyecto), reproducible.
- **El core aporta observabilidad**: un readiness check que compara "GPU
  presente en el host" vs "el backend esta usando la GPU" (via `/api/ps` u
  equivalente) y AVISA si hay GPU pero el modelo corre en CPU. keep_alive y
  parametros del backend se pasan declarativamente por `profile.extra`
  (ADR 0003). [Pendiente de implementar.]
- **El core NO instala** el backend (Ollama/Docker): eso vive en el despliegue,
  documentado + compose de referencia.

## Motivo

El rendimiento (GPU) es critico cuando se integren consumidores del core. Un
fallo silencioso a CPU debe ser **visible** (en el lab, un `daemon-reload`
rompio el cgroup de GPU del contenedor Ollama -> NVML Unknown Error -> CPU;
`docker restart` lo recupero). La compartimentacion via Docker facilita la
administracion. La agnosticidad del backend mantiene el core limpio y portable.

## Consecuencia

- Guia "desde cero" del backend con GPU + `deploy/ollama.compose.yaml` de
  referencia (documentacion, no parte del core).
- Caveat documentado: un `systemctl daemon-reload` del host puede tirar la GPU
  del contenedor (NVML Unknown Error) -> `docker restart <contenedor>`. El
  readiness del core lo hara visible.
- readiness check y provisioning quedan como mejoras del core, a disenar.
