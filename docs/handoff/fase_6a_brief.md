# Handoff de implementacion: fase 6a (vertical minimo de inferencia)

Destinatario: agente codificador (Codex/Sonnet).
Autor: Claude Code (Opus), rol disenador.
Verificacion: Opus, contra la bateria de `eval/`.

Este brief es autocontenido pero NO sustituye a los documentos. Antes de
codificar, lee `CORE_CONTRACT.md`, `ARCHITECTURE.md` y los ADRs citados.

## Objetivo

Implementar el corte end-to-end mas fino: `prompt.run` por CLI contra un
backend real via adaptador OpenAI-compatible. Es la senal #1 de
`VISION_FUNCIONAL.md` ("responde por CLI con modelos locales").

## Dentro de fase 6a

Cadena: `CLI -> prompt_runtime -> ModelAdapter (openai_compatible) -> backend`,
con dominio/modelo DECLARADO explicitamente (sin router todavia; `prompt.run`
admite dominio declarado por contrato).

Componentes minimos:

1. Carga de configuracion YAML (ADR 0014): `models`, `profiles`,
   `identity_defaults`, `telemetry`. Resolucion de `${ENV_VAR}` en `endpoint`.
   (La validacion completa `config.validate` es fase 6b; aqui basta cargar.)
2. Identidad de request (ADR 0011): `user_id`, `service`, `session_id`,
   `domain_tag`, `namespace`, con default desde `identity_defaults`.
3. `ModelAdapter` (ADR 0003): interfaz + `OpenAICompatibleAdapter` +
   `FakeAdapter` (para conformance). El adaptador emite el flujo de eventos
   D2 (`token`, `step`, `trace`, `done`, `error`); el modo bloqueante colecta
   hasta `done` (ADR 0004).
4. `prompt_runtime`: orquesta el adaptador y produce la salida de `prompt.run`
   (respuesta, modelo usado, dominio usado, parametros efectivos, traza).
5. `MemoryPort` + `NullMemoryAdapter` (ADR 0011): conectado, no-op. Presente
   para no crear deuda; no implementa memoria.
6. Telemetria (ADR 0010/0015): escritura CSV (18 columnas) + JSONL (contenido)
   por request. Best-effort: un fallo de traza NO rompe la inferencia salvo
   `strict_mode`. `token` no va a CSV.
7. CLI: comando para ejecutar `prompt.run` (prompt + dominio/modelo declarado),
   leyendo la config.

## Fuera de fase 6a (NO implementar aqui)

- `domain_router` / ruteo por reglas -> fase 6b.
- Politica de fallback y `ModelUnavailable` (ADR 0005) -> fase 6b.
- `config.validate` completo -> fase 6b.
- Runner de `eval.run` -> fase 6b.
- MCP / REST -> fase 7.
- Cualquier logica de memoria, RAG, agentes -> fuera del core.

## Layout sugerido (ajustable; sin abstracciones innecesarias)

```
src/ianest_core/
  config/{loader.py, schema.py}
  identity.py
  adapters/{base.py, openai_compatible.py, fake.py}
  runtime/prompt_runtime.py
  memory/{port.py, null_adapter.py}
  telemetry/trace.py
  registry/model_registry.py   # minimo: listar modelos de config
  cli.py
tests/
```

## Blanco de aceptacion (como se verifica)

Criterio de salida de fase 6a (`PLAN.md`):

1. `prompt.run` responde por CLI con un modelo real en el backend de
   desarrollo (smoke de calidad). Corresponde a `eval/battery/smoke.yaml`
   (`smoke_general_nonempty`). El smoke real lo dispara el usuario cuando
   autorice el backend (ver "Restricciones").
2. Genera traza por request con identidad (ADR 0015).
3. La pista de conformance aplicable pasa contra `FakeAdapter`, reproducible.
   De `eval/battery/conformance.yaml`, en fase 6a aplica:
   - `identity_propagated_to_trace` (prompt.run + identidad en traza).
   Los demas casos (ruteo, fallback, ModelUnavailable, config.validate,
   model.list) son de fase 6b y NO son blanco de 6a.

Se espera ademas un test unitario de `prompt_runtime` con `FakeAdapter` que
demuestre la coleccion bloqueante del flujo D2 y los campos de trazabilidad.

## Restricciones y convenciones

- Python 3.13; pip + venv; pytest (ADR 0012). Sin linter/type-checker.
  `pyproject.toml` minimo (PEP 621), paquete instalable con `pip install -e .`.
- Identificadores y claves en ingles snake_case (ADR 0016). Prosa/comentarios
  en espanol sin tildes.
- Filosofia UNIX: modulos pequenos, probables de forma aislada. Cabecera en
  scripts no triviales (`CONVENCIONES.md`).
- Secretos/endpoints por env var; nunca en YAML versionado. La config real y
  el `.env` viven fuera del repo (`local/`, `.env.example` como plantilla).
- NO conectar al host de laboratorio sin instruccion explicita del usuario. La
  pista conformance no necesita red ni GPU; usar `FakeAdapter`.

## Contexto de entorno para el codificador

Fase 6a NO necesita los detalles concretos del laboratorio para codificar:

- La pista conformance usa `FakeAdapter`: sin red, sin GPU, sin endpoint.
- El adaptador real se escribe contra `OPENAI_COMPAT_BASE_URL` (env var), no
  contra una IP. Endpoint y modelo son configuracion, no codigo.
- El smoke real lo dispara el usuario cuando autorice el backend.

Contexto saneado disponible EN el repo (versionado): caracteristicas
genericas del host en ADR 0013; nombres de variables en `.env.example`;
esquema de config en ADR 0014.

Contexto local (solo si trabajas en la maquina del usuario): los detalles
concretos (IP, specs, endpoint Ollama y su puerto) estan en
`local/dev_environment.md`, fuera de git. Si corres en otro checkout no lo
veras, y no lo necesitas para 6a. En ningun caso conectar al host sin permiso
explicito del usuario.

## Handoff de vuelta

Al terminar, Opus verifica: ejecuta la pista conformance aplicable y revisa la
traza generada contra el ADR 0015. El smoke real se valida con el usuario.
