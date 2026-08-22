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
Catalogo de dominios. Campos: `id`, `description`, `preferred_model`,
`fallback_models`, `profile`, `status`.

    domains:
      - id: general
        description: "Preguntas generales y todo lo que no encaje en otro dominio"
        preferred_model: local_llama
        fallback_models: []
        profile: default
        status: active

**`description` no es documentacion: es la entrada del clasificador.** Desde
ADR 0043 el enrutado es SEMANTICO -un modelo lee las descripciones y elige por
sentido-, asi que una descripcion vaga produce un enrutado vago. Escribelas para
que se distingan entre si.

El enrutado por palabras clave se RETIRO en ADR 0043. El campo `routing_rules`
sigue aceptandose en la config para no romper ficheros antiguos, pero **se
ignora**: no enruta nada.

Si el `preferred_model` no esta disponible, se usa el primer `fallback_models`;
si ninguno, error `ModelUnavailable`.

### router y default_domain
Obligatorios para que el enrutado semantico funcione (ADR 0043), y viven en la
raiz de la config, no dentro de `domains`.

    router: { model: local_llama, profile: default }
    default_domain: general

`router` declara QUIEN clasifica: un modelo del roster o un dominio, con su
perfil. Con un solo modelo declarado, el router clasifica contra ese mismo
modelo.

`default_domain` designa EXPLICITAMENTE el dominio de reserva: es donde cae
`prompt.run` cuando no se le declara modelo ni dominio, y donde cae el router
cuando no puede interpretar su propia respuesta. Antes se asumia un dominio
llamado `general` por convencion; ADR 0043 retiro ese nombre magico, asi que hay
que declararlo.

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

Cualquier clave ADICIONAL del perfil viaja al backend como parametro de
generacion, tal cual, salvo las tres que son limites del core y no del modelo
(`max_iterations`, `max_time_s`, `max_context_tokens`). Ahi es donde se declara,
por ejemplo, un `seed` si tu backend lo honra. El core no modela esos
parametros: los transporta.

Un dominio servido por un modelo de RAZONAMIENTO necesita perfil propio con
presupuesto mayor. Ese modelo emite su cadena de pensamiento antes de la
respuesta, y el core la sanea en origen (ADR 0042): si el techo de tokens llega
antes de que la cadena cierre, la respuesta util es cadena VACIA con
`finish_reason: length`.

### orchestration
Objetivos y limites de `task.run`. El bloque base es el nivel de esfuerzo
`medium`. `default_effort` selecciona el nivel cuando la peticion no envia
`effort`; su valor de fabrica es `medium`.

    orchestration:
      planner: { model: local_llama, profile: default }
      combiner: { model: local_llama, profile: default }
      max_subtasks: 6
      max_iterations: 2
      max_replans: 1
      max_time_s: 120
      max_parallel: 2
      token_budget: { base: 2000, per_subtask: 3000 }
      default_effort: medium
      effort:
        low:
          max_subtasks: 3
          max_iterations: 1
          max_replans: 0
          max_time_s: 30
          coverage: { max_chunks: 4, max_retries_per_unit: 1 }
        high:
          max_subtasks: 12
          max_iterations: 4
          max_replans: 2
          max_time_s: 480
          coverage: { max_chunks: 16, max_retries_per_unit: 3 }
      coverage:
        validator: { model: local_llama, profile: default }
        units_per_chunk: 3
        max_chunks: 8
        max_retries_per_unit: 2
        max_no_progress_iterations: 2

La precedencia se aplica campo a campo: un valor declarado en el nivel
sustituye al de la base; un valor ausente hereda la base. Un nivel del
vocabulario `low | medium | high` que no figure en `effort` tambien resuelve a
la base, sin error.

El esfuerzo gobierna trabajo autorizado: `max_subtasks`, `max_iterations`,
`max_replans`, `max_time_s`, `coverage.max_chunks` y
`coverage.max_retries_per_unit`. No cambia `max_parallel`,
`coverage.units_per_chunk` ni `coverage.max_no_progress_iterations`, que son
ejes de maquina. Tampoco cambia `token_budget`: `base` y `per_subtask` miden el
coste y no son una politica de esfuerzo.

Las renegociaciones de PLAN y EVALUATE no son parametros de configuracion:
cada etapa dispone de una por tarea, fijada en contrato (ADR 0041). Son
independientes y se observan como `plan_attempts` y `evaluation_attempts`.

Determinismo del plan: el planificador es un modelo muestreado, asi que el mismo
prompt con el mismo `effort` puede dar planes de tamano distinto, y eso mueve el
coste. Es palanca del OPERADOR, no del contrato: dale al planificador un perfil
con `temperature: 0.0` (y `seed`, si tu backend lo honra). Para medir `task.run`
de forma reproducible hay ademas una via del core: congelar el plan con
`task.plan` y pasarselo a `task.run`, que lo acepta tal cual.

### identity_defaults
`user_id`, `service` por defecto.

### telemetry
`csv_path`, `jsonl_path`, `rotation` (`size`|`date`), `strict_mode`.

## Secretos
Nunca pongas endpoints ni credenciales en el YAML: usa `${VARIABLE}` y define
el valor en `.env` (no versionado).
