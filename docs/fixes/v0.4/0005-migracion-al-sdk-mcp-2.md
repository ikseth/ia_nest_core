# 0005: migrar al SDK de MCP 2.x

Estado: propuesta
Tipo: migracion de dependencia (afecta a la interfaz MCP, no al contrato)
Impacto de version: patch si la paridad se conserva
Version objetivo: sin asignar

## Problema

`pyproject.toml` declaraba `mcp>=1.28.1` **sin tope superior**. El SDK publico
una version 2.0.0 que **retira `mcp.server.fastmcp`**, que es lo que
`src/ianest_core/mcp_server.py` importa. Consecuencia: cualquier instalacion
limpia a partir de esa publicacion se lleva la 2.0.0 y la interfaz MCP queda
rota.

Detectado estrenando el instalador en una maquina virtual limpia. En esa maquina:

    mcp 2.0.0 instalado
    ModuleNotFoundError: No module named 'mcp.server.fastmcp'
    ianest-<instancia>-mcp.service en bucle de reinicio
    6 tests fallando, entre ellos el gate bidireccional de ADR 0046

En un entorno de desarrollo con el venv creado hace meses, `mcp` sigue clavado en
1.28.1 y **todo pasa**. Por eso no lo vio nadie: la bateria y los gates corren
contra un venv que ya tenia la version buena.

Leccion, mas alla de esta dependencia: **una suite verde en un venv viejo no dice
nada sobre una instalacion nueva.** Es el mismo argumento que sostiene estrenar
en laboratorio en vez de dar por buena la maquina de desarrollo.

## Lo ya hecho, que NO es esta ficha

Se acoto la dependencia a `mcp>=1.28.1,<2` para que las instalaciones limpias
vuelvan a funcionar. Eso detiene el problema; no lo resuelve.

## Cambio

Migrar `mcp_server.py` al API de MCP 2.x y levantar el tope, o fijar el rango que
corresponda cuando se conozca la superficie nueva.

Puntos a resolver durante la migracion, todos verificables:

- Equivalente de `FastMCP` en 2.x, y como se declaran herramientas y su firma.
- El transporte SSE: si sigue existiendo con el mismo nombre y forma.
- El gate bidireccional de ADR 0046 debe seguir comparando catalogo y
  herramientas **en las dos direcciones**. Si el API nuevo no permite leer las
  firmas registradas, hay que decidir como se conserva el gate ANTES de migrar:
  sin el, la deriva entre catalogo e interfaz vuelve a ser posible y esa es la
  razon por la que existe.
- `runtime.health` declara la version del protocolo MCP (ADR 0006): comprobar que
  sigue siendo obtenible y que su valor cambia como debe.

## Criterios de aceptacion

- `pytest` en verde en una maquina LIMPIA, no solo en un venv existente.
- Los seis tests que hoy fallan con 2.0.0 pasan.
- Paridad CLI/REST/MCP intacta, y el gate de ADR 0046 sigue siendo bidireccional.
- La conformidad no se mueve, o se declara si se moviera.
- El instalador levanta el servicio MCP y este ESCUCHA, no solo figura activo.

## Archivos previstos

- `src/ianest_core/mcp_server.py`
- `pyproject.toml`
- `tests/test_phase_7.py`, `tests/test_capabilities.py`, `tests/test_task_interfaces.py`
- `CHANGELOG.md`

## No cubre

- El contrato publico del core, que no cambia por migrar de SDK.
- La verificacion en maquina limpia como practica general, que da para su propia
  decision: hoy nada obliga a que la suite se ejecute alguna vez contra
  dependencias recien resueltas.

## Resultado

Pendiente.
