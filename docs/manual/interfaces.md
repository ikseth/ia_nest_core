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

## MCP (SDK oficial)

Por defecto **stdio** (lo lanza el cliente MCP):

    python -m ianest_core.mcp_server

O como **servicio de red por SSE**:

    python -m ianest_core.mcp_server --transport sse --host 127.0.0.1 --port 8090

Herramientas: `prompt.run`, `domain.route`, `model.list`, `domain.list`,
`config.validate`, `eval.run`, `runtime.health` (con salida estructurada). La
version de protocolo se declara en `runtime.health`.

## Como servicio (systemd, Linux)

El instalador puede generar unidades systemd para arrancar REST y MCP-SSE de
forma persistente:

    bash install.sh --service                              # puertos por defecto: REST 8000, MCP 8090
    bash install.sh --service --rest-port 8000 --mcp-port 8090

Genera `ianest-rest.service` e `ianest-mcp.service` (con `EnvironmentFile=.env`
y `Restart=on-failure`). Como root los escribe en `/etc/systemd/system` y hace
`daemon-reload`, pero **no los habilita ni arranca** (lo decides tu):

    sudo systemctl enable --now ianest-rest.service ianest-mcp.service

Sin root, los genera en `dist/systemd/` e indica como instalarlos.
