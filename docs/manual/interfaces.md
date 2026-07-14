# Interfaces REST y MCP

Requieren los extras: `bash install.sh --interfaces`. Ambas exponen las mismas
capacidades que la CLI (paridad), sin logica propia.

Antes de arrancar, exporta el endpoint (los servidores NO auto-cargan `.env`):

    export OPENAI_COMPAT_BASE_URL=http://localhost:11434/v1
    # o: source .env

Ambos servidores usan `config/core.yaml` por defecto; arrancalos desde la raiz
del repo.

## REST (Starlette + uvicorn)

    uvicorn --factory ianest_core.rest:create_app --host 127.0.0.1 --port 8000

Endpoints:
- `POST /prompt/run`      `{prompt, domain|model, identity?}`
- `POST /prompt/stream`   igual, respuesta en SSE (streaming)
- `POST /domain/route`    `{prompt}`
- `GET  /model/list` , `GET /domain/list`
- `POST /config/validate` , `POST /eval/run` `{track?}`
- `GET  /runtime/health`

Ejemplo:

    curl -s http://127.0.0.1:8000/runtime/health
    curl -s -X POST http://127.0.0.1:8000/prompt/run \
      -H 'Content-Type: application/json' \
      -d '{"prompt":"Hola","domain":"general"}'

## MCP (SDK oficial, stdio)

    python -m ianest_core.mcp_server

Arranca un servidor MCP por stdio. Un cliente MCP puede invocar las
herramientas `prompt.run`, `domain.route`, `model.list`, `domain.list`,
`config.validate`, `eval.run`, `runtime.health` (con salida estructurada). La
version de protocolo se declara en `runtime.health`.
