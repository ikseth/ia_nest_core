# Configuracion

La forma rapida de crear la configuracion es `ianest init` (ver
[cli.md](cli.md)); esta pagina describe el formato para editarla a mano.

La configuracion es un YAML declarativo. Parte de un ejemplo y validalo:

    cp config/core.example.yaml config/core.yaml         # minimo (un modelo)
    # o el de laboratorio, con roster multi-modelo por dominio:
    cp config/core.lab.example.yaml config/core.yaml
    ianest --config config/core.yaml config validate

## Secciones

### models
Campos: `id`, `provider`, `adapter` (`openai_compatible`), `endpoint` (por env
var), `model_name` (tag en el backend), `capabilities`, `profile`.

    models:
      - id: local_llama
        provider: ollama
        adapter: openai_compatible
        endpoint: ${OPENAI_COMPAT_BASE_URL}
        model_name: llama3.1:8b
        capabilities: [chat]
        profile: default

### domains
Enrutado por dominio. Campos: `id`, `description`, `preferred_model`,
`fallback_models`, `profile`, `routing_rules` (`keywords`/`tags`), `status`.

    domains:
      - id: general
        description: "Dominio general"
        preferred_model: local_llama
        fallback_models: []
        profile: default
        routing_rules: { keywords: [] }
        status: active

Si el prompt contiene una keyword del dominio, se enruta ahi. Si el
`preferred_model` no esta disponible, se usa el primer `fallback_models`; si
ninguno, error `ModelUnavailable`.

### profiles
Parametros de generacion, limites y `system` opcional. Campos: `id`,
`temperature`, `max_tokens`, `top_p`, `max_iterations`, `max_time_s`,
`max_context_tokens`, y `system` (system prompt, p.ej. forzar idioma).

    profiles:
      - id: default
        temperature: 0.2
        max_tokens: 512
        top_p: 1.0
        max_iterations: 4
        max_time_s: 60
        max_context_tokens: 4096
        system: "Responde siempre en espanol."

### identity_defaults
`user_id`, `service` por defecto.

### telemetry
`csv_path`, `jsonl_path`, `rotation` (`size`|`date`), `strict_mode`.

## Secretos
Nunca pongas endpoints ni credenciales en el YAML: usa `${VARIABLE}` y define
el valor en `.env` (no versionado).
