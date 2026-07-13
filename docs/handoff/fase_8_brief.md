# Handoff de implementacion: fase 8 (bucle de razonamiento, reasoning.run)

Destinatario: agente codificador (Codex/Sonnet).
Autor: Claude Code (Opus), rol disenador.
Verificacion: Opus.
Base: `main` con fases 1-7 integradas y verificadas. Reutiliza el codigo
existente.

Autocontenido pero NO sustituye a los documentos. Lee `CORE_CONTRACT.md`
(`reasoning.run`), `ARCHITECTURE.md` (`reasoning_loop`), los ADRs citados y el
codigo de `prompt_runtime`/`service` en `src/ianest_core/`.

## Objetivo

Implementar `reasoning.run` (CORE_CONTRACT): razonamiento iterativo controlado
y observable, SIN herramientas (ADR 0022), con el diseno del ADR 0023
(borrador y refinamiento).

## Dentro de fase 8

1. reasoning_loop / `reasoning.run` (ADR 0023):
   - Mecanismo borrador-y-refinamiento: iter 1 = borrador; iter k>1 =
     critica + refina el borrador actual.
   - Parada: el modelo senala `done` (flag estructurado) + limites duros de
     iteraciones, tiempo y presupuesto de tokens (ADR 0008). Al exceder un
     limite, parar con `stop_reason` tipado (`model_done` | `max_iterations` |
     `max_time` | `max_context_tokens`).
   - Observabilidad: cada iteracion emite un evento `step` por el flujo D2
     (ADR 0004/0015) con `{iteration, output, done}`; el modo bloqueante
     colecta hasta `done`. `capability="reasoning.run"`.
   - Limites configurables por perfil (ADR 0014): `max_iterations`,
     `max_time_s`, `max_context_tokens` (ya en el esquema).
   - "Desactivar pasos no necesarios": configurable (p.ej. `max_iterations=1`
     = solo borrador, sin refinamiento).
   - Reutiliza la resolucion/adaptador/telemetria de `PromptRuntime`
     (`_prepare`, `run_blocking` o el `stream` del adaptador).
2. Exposicion por las tres interfaces via la capa de servicio
   (`service.run_reasoning` / `stream_reasoning`): CLI (`ianest reasoning run`
   / `stream`), REST (`/reasoning/run`, `/reasoning/stream` SSE), MCP (tool
   `reasoning.run`). Sin logica en las interfaces (paridad, fase 7).
3. Casos de conformance para `reasoning.run` en `eval/battery/`: cortes por
   `model_done` y por `max_iterations` (deterministas con un `FakeAdapter`
   scriptable). Presupuesto de tokens: caso con limite bajo. (El tiempo es
   dificil de hacer determinista; si lo incluyes, con margen amplio o
   mockeando el reloj.)

## Pieza a proponer (no inferir en silencio)

La convencion de prompting para la senal `done` del modelo (p.ej. pedirle una
salida estructurada `{output, done}` o un marcador). Debe ser simple y con
fallback robusto: si no se puede parsear el `done`, tratar como no-done y
seguir hasta los limites. Proponla y PARA y pregunta si dudas.

## Fuera de fase 8 (NO implementar)

- Invocacion de herramientas / `tool_contracts` (diferido, ADR 0022).
- Compactacion de contexto / escritura a memoria (diferida, ADR 0023): el
  presupuesto es PARADA, no compactacion.
- RAG, agentes, etc.

## No reinventar (ya fijado)

- Diseno del bucle: ADR 0023.
- Streaming como primitiva (ADR 0004); evento `step` y esquema de traza
  (ADR 0015).
- Errores (ADR 0020); capa de servicio y paridad (fase 7).
- ModelAdapter (ADR 0018).

## Blanco de aceptacion

- `reasoning.run` corta por cada limite (`model_done`, `max_iterations`,
  `max_context_tokens`) y registra `stop_reason` en traza; conformance
  determinista con `FakeAdapter`, reproducible (digest estable, ADR 0017).
- Emite eventos `step` observables por el flujo D2; el bloqueante colecta.
- Paridad CLI/REST/MCP (test de paridad service vs interfaces).
- `pytest` en verde con extras; core minimo en verde sin extras.
- `eval.run` sigue en verde, incluyendo los nuevos casos.

## Restricciones y convenciones

- Python 3.13; pip + venv; pytest. Identificadores/claves en ingles
  snake_case; prosa en espanol sin tildes. Modulos pequenos; reutiliza
  6a/6b/7.
- Repo PUBLICO: nada interno en archivos versionados; endpoints/secretos por
  env var. Corres en esta maquina: puedes leer `local/`; NO conectes al host;
  usa fakes para los tests.
- Ambiguedad o contradiccion en los docs -> PARA y preguntame.

## Entrega y handoff de vuelta

Rama nueva desde `main` (p.ej. `fase-8-reasoning`), tests en verde, y una nota
con las decisiones tomadas (incluida la convencion de `done`). Opus verifica
cortes por limite, observabilidad por pasos, paridad y digest reproducible.
