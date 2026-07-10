# Alcance del core

## Dentro del core

- Catalogo de modelos.
- Perfiles de dominio.
- Router de prompts.
- Runtime de inferencia.
- Bucle de razonamiento controlado.
- Interfaz MCP del core.
- Configuracion JSON/YAML.
- Scripts de instalacion.
- Deteccion de GPU/runtime.
- Evaluacion.
- Trazabilidad.
- Contratos minimos para herramientas externas.

## Fuera del core

- Home Assistant.
- Nextcloud.
- RAG.
- Busqueda web.
- Frontend completo.
- Agentes autonomos.
- Memoria avanzada.
- Consciencia.
- Automatizacion de sistemas.
- Crawling web complejo.
- Gestion de secretos productiva.

## Frontera

El core puede llamar herramientas externas mediante contratos, pero no debe
absorber su logica interna.

RAG y busqueda web no definen el core. Si se incorporan, sera desde
`ia_nest_core_extended` o equivalente.
