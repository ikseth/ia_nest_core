# CLI (referencia rapida)

Todos los comandos aceptan `--config RUTA` (por defecto `config/core.yaml`) y
`--json` (salida en JSON).

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
