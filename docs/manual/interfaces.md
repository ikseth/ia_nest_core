# Interfaces REST y MCP

Requieren los extras: `bash install.sh --interfaces`. Ambas exponen las mismas
capacidades que la CLI (paridad), sin logica propia.

Ambos servidores cargan `.env` del directorio actual automaticamente y usan
`config/core.yaml` por defecto: arrancalos desde la raiz del repo (donde estan
`.env` y `config/core.yaml`).

Para arrancarlos como servicio persistente (systemd), ver
[instalacion.md](instalacion.md).

## REST (Starlette + uvicorn)

    uvicorn --factory ianest_core.rest:create_app --host 127.0.0.1 --port 8000

Endpoints:
- `POST /prompt/run`      `{prompt, domain|model, identity?}`
- `POST /prompt/stream`   igual, respuesta en SSE (streaming)
- `POST /task/run`        `{prompt, mode?, effort?, identity?}`, respuesta JSON
- `POST /task/stream`     igual, respuesta en SSE (streaming)
- `POST /domain/route`    `{prompt}`
- `GET  /model/list` , `GET /domain/list`
- `GET  /capability/list`
- `POST /config/validate` , `POST /eval/run` `{track?}`
- `GET  /runtime/health`

Ejemplo:

    curl -s http://127.0.0.1:8000/runtime/health
    curl -s -X POST http://127.0.0.1:8000/prompt/run \
      -H 'Content-Type: application/json' \
      -d '{"prompt":"Hola","domain":"general"}'

## MCP (SDK oficial)

Por defecto **stdio** (lo lanza el cliente MCP):

    python -m ianest_core.mcp_server

O como **servicio de red por SSE**:

    python -m ianest_core.mcp_server --transport sse --host 127.0.0.1 --port 8090

Herramientas: `capability.list`, `prompt.run`, `reasoning.run`, `task.run`,
`domain.route`, `model.list`, `domain.list`, `config.validate`, `eval.run` y
`runtime.health` (con salida estructurada). `task.stream` no se expone por MCP.
La version de protocolo se declara en `runtime.health`.
