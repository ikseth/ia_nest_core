# CLI (referencia rapida)

`ianest` es el comando de la CLI, instalado DENTRO del entorno virtual (no es
un fichero del repo). Activa el venv y estara disponible en el PATH:

    source .venv/bin/activate
    ianest --help

Sin activar el venv puedes usarlo igual con `.venv/bin/ianest ...` o
`python -m ianest_core.cli ...`.

## Estructura de un comando

    ianest [--config RUTA] GRUPO ACCION [opciones]

`GRUPO` y `ACCION` son obligatorios (dos palabras). Ejemplos: `prompt run`,
`reasoning run`, `domain route`, `domain list`, `model list`,
`config validate`, `eval run`, `runtime detect`, `runtime health`.

NO funciona `ianest --prompt "..."` suelto: le falta el grupo y la accion.
Lo correcto es `ianest ... prompt run --prompt "..."`.

Antes de usar la CLI necesitas un `config/core.yaml` y `.env`: la forma rapida
es `ianest init` (ver abajo). Ver tambien [configuracion.md](configuracion.md)
e [instalacion.md](instalacion.md).

Todos los comandos aceptan `--config RUTA` (por defecto `config/core.yaml`) y
`--json` (salida en JSON).

## Inicializar (crear config)

    ianest init --endpoint http://localhost:11434/v1 --template lab

Crea `config/core.yaml` y `.env`, y valida. Es la excepcion a "dos palabras":
`init` es un comando de una sola palabra.

## Inferencia

    # responder un prompt: por modelo o dominio declarado; sin ninguno, auto-route
    ianest --config config/core.yaml prompt run --prompt "Hola" --domain general
    ianest --config config/core.yaml prompt run --prompt "Hola" --model local_llama --json

    # razonamiento iterativo (borrador + refinamiento, con los limites del perfil)
    ianest --config config/core.yaml reasoning run --prompt "Resuelve ..." --domain matematicas --json

Flags de identidad (opcionales): `--user-id`, `--service`, `--session-id`,
`--domain-tag`, `--namespace`.

## Enrutado e inventario

    ianest --config config/core.yaml domain route --prompt "..."   # que dominio/modelo elegiria
    ianest --config config/core.yaml model list                    # modelos y disponibilidad
    ianest --config config/core.yaml domain list                   # dominios

## Configuracion y evaluacion

    ianest --config config/core.yaml config validate               # valida el YAML
    ianest --config config/core.yaml eval run --track conformance  # bateria determinista (fakes)
    ianest --config config/core.yaml eval run --track smoke        # bateria contra backend real

## Runtime

    ianest --config config/core.yaml runtime detect                # GPU, runtime, backend
    ianest --config config/core.yaml runtime health                # estado + version de protocolo MCP
