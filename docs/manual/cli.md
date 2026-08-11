# CLI (referencia rapida)

`ianest` es el comando de la CLI, instalado DENTRO del entorno virtual (no es
un fichero del repo). Activa el venv y estara disponible en el PATH:

    source .venv/bin/activate
    ianest --help

Sin activar el venv puedes usarlo igual con `.venv/bin/ianest ...` o
`python -m ianest_core.cli ...`.

## Ayuda por niveles

La ayuda es jerarquica para mantener cada pantalla pequena y relevante:

    ianest --help                    # indice de grupos
    ianest reasoning --help          # acciones del grupo
    ianest reasoning stream --help   # detalle de una accion y sus opciones

El mismo patron funciona con todos los grupos. Consultar `--help` no carga la
configuracion ni contacta con el backend.

## Estructura de un comando

    ianest [--config RUTA] GRUPO ACCION [opciones]

`GRUPO` y `ACCION` son obligatorios (dos palabras). Ejemplos: `prompt run`,
`prompt stream`, `reasoning run`, `reasoning stream`, `task run`,
`domain route`, `domain list`, `model list`, `model pull`, `config validate`,
`eval run`, `runtime detect`, `runtime health`.

NO funciona `ianest --prompt "..."` suelto: le falta el grupo y la accion.
Lo correcto es `ianest ... prompt run --prompt "..."`.

Antes de usar la CLI necesitas un `config/core.yaml` y `.env`: la forma rapida
es `ianest init` (ver abajo). Ver tambien [configuracion.md](configuracion.md)
e [instalacion.md](instalacion.md).

`--config RUTA` es una opcion global, se escribe antes del grupo y usa
`config/core.yaml` por defecto. Las acciones operativas aceptan `--json` para
obtener salida estructurada; `init` no produce salida JSON. En acciones con
flujo, stdout contiene la respuesta y stderr el progreso. El espectro de salida
es: `--quiet` suprime el progreso, por defecto se muestran hitos concisos,
`--verbose` muestra el detalle por paso y antepone a cada linea de progreso en
stderr el tiempo acumulado desde el primer evento (`[  0.0s]`), y `--json`
emite los eventos estructurados completos a stdout. Ninguno de `--quiet` ni
`--verbose` afecta a la respuesta. El reloj no se aplica a stdout, JSON ni a
los avisos de corte o degradacion.

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
    ianest --config config/core.yaml reasoning stream --prompt "Resuelve ..." --quiet

    # respuesta por fragmentos; stdout se puede redirigir limpio a un fichero
    ianest --config config/core.yaml prompt stream --prompt "Hola" --domain general > respuesta.txt

Flags de identidad (opcionales): `--user-id`, `--service`, `--session-id`,
`--domain-tag`, `--namespace`.

## Tareas

    # pipeline multi-modelo; --mode acepta pipeline (por defecto) o coverage
    ianest --config config/core.yaml task run --prompt "Analiza ..." --mode pipeline

`task run` avisa por stderr de cada degradacion declarada (por ejemplo, si el
evaluador no logra emitir una decision entendible y el core conserva el
resultado asumiendo `done`). La respuesta sigue en stdout y el codigo de salida
es cero: una degradacion entrego resultado; no es un corte. Los cortes por
limite se anuncian tambien por stderr, pero terminan con codigo distinto de
cero. `--json` transporta los campos `requirements_covered`,
`uncovered_requirements`, `plan_attempts`, `evaluation_attempts` y
`degradations` sin logica adicional de interfaz.

## Enrutado e inventario

    ianest --config config/core.yaml domain route --prompt "..."   # que dominio/modelo elegiria
    ianest --config config/core.yaml model list                    # modelos y disponibilidad
    ianest --config config/core.yaml model pull                    # descarga los modelos declarados ausentes
    ianest --config config/core.yaml domain list                   # dominios

## Configuracion y evaluacion

    ianest --config config/core.yaml config validate               # valida el YAML
    ianest --config config/core.yaml eval run --track conformance  # bateria determinista (fakes)
    ianest --config config/core.yaml eval run --track smoke        # bateria contra backend real

## Runtime

    ianest --config config/core.yaml runtime detect                # GPU, runtime, backend
    ianest --config config/core.yaml runtime health                # estado + version de protocolo MCP
