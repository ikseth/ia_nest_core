# Decision 0026: servicios systemd (REST y MCP) y transporte SSE para MCP

Fecha: 2026-07-14

## Decision

- `install.sh` admite `--service`: genera unidades systemd para las interfaces
  (Linux/systemd por ahora), con `EnvironmentFile=<repo>/.env`,
  `WorkingDirectory` del repo, `ExecStart` desde el venv y `Restart=on-failure`.
  Dos unidades: REST (uvicorn) y MCP. Requiere root para instalarlas via
  systemctl; sin root, las genera e indica los comandos.
- `mcp_server` admite transporte de red **SSE** ademas de stdio, por argumentos
  (`--transport {stdio,sse}`, `--host`, `--port`). Por defecto stdio (compat).
  La unidad de MCP lo arranca en modo SSE.
- Los entry points (CLI, REST `create_app`, MCP main) auto-cargan `.env` del
  directorio de trabajo via un helper compartido (cierra el gap de `.env` en
  los servidores; el unit ademas usa `EnvironmentFile`).

## Motivo

Facilitar el lanzamiento persistente y robusto de las interfaces (adoptar
systemd, ADR 0009), exponer MCP por red para clientes remotos, y unificar la
carga de `.env`. Linux/systemd por ahora; portable a otros init despues.

## Consecuencia

- Nuevos artefactos: plantillas de unit systemd generadas por `install.sh`.
- MCP con dos transportes: stdio (cliente local) y SSE (servicio de red).
- Helper `.env` compartido (refactor del cargador de la CLI).
- La instalacion de servicios requiere root; `install.sh --service` no
  habilita/arranca los servicios automaticamente (lo decide el usuario).
- Documentar en `docs/manual/interfaces.md` tras verificar.
