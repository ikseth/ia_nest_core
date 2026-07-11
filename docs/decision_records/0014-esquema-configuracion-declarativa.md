# Decision 0014: esquema de configuracion declarativa

Fecha: 2026-07-10

## Decision

La configuracion del core es declarativa en YAML (legible, admite
comentarios). Claves en ingles snake_case (ADR 0016). `config.validate`
(CORE_CONTRACT) la comprueba antes de arrancar. Secciones minimas:

- `models`: lista de modelos.
  - `id`, `provider`, `adapter` (`openai_compatible`), `endpoint`,
    `model_name` (id del modelo en el backend), `capabilities` (lista),
    `profile` (perfil recomendado, referencia).
- `domains`: lista de dominios.
  - `id`, `description`, `preferred_model` (ref a `models.id`),
    `fallback_models` (lista de refs, ADR 0005), `profile` (ref),
    `routing_rules` (declarativas: `keywords`/`tags`), `status`.
- `profiles`: conjuntos de parametros nombrados.
  - `id`, parametros de sampling (`temperature`, `max_tokens`, `top_p`...),
    `extra` (opaco, ADR 0003), y limites de razonamiento
    (`max_iterations`, `max_time_s`, `max_context_tokens`, ADR 0008).
- `identity_defaults`: identidad local por defecto (ADR 0011):
  `user_id`, `service` (p.ej. `local_cli`).
- `telemetry`: rutas de sinks CSV/JSONL, rotacion (`size`/`date`),
  `strict_mode` (ADR 0010).

## Gestion de endpoints y secretos

- `endpoint` y cualquier credencial se dan por referencia a variable de
  entorno (p.ej. `endpoint: ${OPENAI_COMPAT_BASE_URL}`), no por valor.
- Ninguna credencial/token se escribe en YAML versionado. Los valores
  concretos viven en `.env` / `local/` (no versionado, ADR 0013).

## Motivo

Configuracion declarativa antes que logica implicita (principio del core).
YAML por legibilidad y comentarios; una sola fuente para modelos, dominios,
perfiles e identidad por defecto; sin secretos en el repo.

## Consecuencia

`config.validate` comprueba: campos requeridos, integridad referencial
(`preferred_model`/`fallback_models`/`profile` existen), resolucion de
variables de entorno referenciadas, e incompatibilidades basicas. El esquema
puede detallarse en su propia pagina al implementar `config.validate`; este
ADR fija la forma. Cambiar el esquema exige decision registrada.
