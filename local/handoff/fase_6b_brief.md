# Handoff de implementacion: fase 6b (ruteo, resiliencia y runner de eval)

Destinatario: agente codificador (Codex/Sonnet).
Autor: Claude Code (Opus), rol disenador.
Verificacion: Opus, contra la bateria de `eval/`.
Base: parte de `main` con la fase 6a ya integrada y verificada.

Autocontenido pero NO sustituye a los documentos. Antes de codificar, lee
`CORE_CONTRACT.md`, `ARCHITECTURE.md`, los ADRs citados y el codigo de 6a en
`src/ianest_core/` (reutilizalo, no lo dupliques).

## Objetivo

Completar el core minimo operable: enrutado por dominios, resiliencia ante
modelo no disponible, validacion de configuracion y el runner que ejecuta la
bateria. Es la senal #2 de `VISION_FUNCIONAL.md` ("enruta dominios
correctamente").

## Dentro de fase 6b

1. `domain_router` (`domain.route`): dado un prompt, propone dominio, modelo,
   confianza, motivo y alternativas (CORE_CONTRACT), usando `routing_rules`
   declarativas de la config (`keywords`/`tags`). Se integra como la via 3 de
   resolucion de `prompt.run` (ADR 0019): sin modelo ni dominio declarados, el
   router decide (o cae al dominio `general`). La decision se registra en la
   traza (evento `route`, ADR 0015).
2. Disponibilidad + fallback (ADR 0005): el registry consulta disponibilidad.
   Si `preferred_model` no esta disponible, intenta `fallback_models` en
   orden; si ninguno, error tipado `ModelUnavailable`. La sustitucion se
   registra en la traza. En conformance la (no)disponibilidad se controla via
   `world.unavailable_models`; en real, via probe del adaptador /
   `runtime.health`. Propon la interfaz de disponibilidad (p.ej. un
   `AvailabilityProvider` inyectable) y PARA y pregunta si hay ambiguedad.
3. `config.validate` (CORE_CONTRACT): valida la config (ADR 0014): campos
   requeridos, integridad referencial (`preferred_model`/`fallback_models`/
   `profile` existen), resolucion de variables de entorno, incompatibilidades
   basicas. Devuelve `ConfigValidationError` con `field`.
4. `model.list` y `domain.list` (CORE_CONTRACT): listados desde el registry.
   No exigen identidad (capacidades administrativas, ADR 0011).
5. `eval.run` (runner, semilla): carga `eval/battery/*.yaml` y
   `eval/fixtures/`, ejecuta la pista conformance contra `FakeAdapter` de
   forma determinista y produce el formato del ADR 0017 (por caso + agregado
   + `conformance_digest` reproducible). La pista smoke corre contra el
   backend real (la lanza el usuario).
6. Menor (diferido de 6a): rotacion de traza por tamano y/o fecha (campo
   `rotation` de `telemetry`, ADR 0015).

## Interfaces / decisiones ya fijadas (no reinventar)

- Resolucion de `prompt.run` (ADR 0019): la via 3 (auto-route) es esta fase.
- Politica de fallo (ADR 0005): preferido > `fallback_models` en orden >
  `ModelUnavailable`; sustitucion en traza.
- Formato de `eval.run` (ADR 0017): por caso + agregado con
  `conformance_digest` reproducible.
- Errores (ADR 0020): usa `ModelUnavailable`, `ConfigValidationError`,
  `RoutingError` ya definidos en `errors.py`.
- Traza (ADR 0015): evento `route`; `token` no va a CSV.
- CLI: subcomandos por capacidad + `--json`. Anade `ianest domain route`,
  `ianest model list`, `ianest domain list`, `ianest eval run`.

## Fuera de fase 6b (NO implementar)

- MCP / REST -> fase 7.
- `reasoning_loop` / `reasoning.run` -> fase posterior (no planificada aun).
- `tool_contracts` -> fase posterior.
- Logica real de memoria, RAG, agentes -> repos externos.

## Blanco de aceptacion

- La bateria conformance COMPLETA pasa contra `FakeAdapter`, reproducible
  (`eval/battery/conformance.yaml`): `routing_keyword_match`,
  `routing_default_domain`, `fallback_used_when_preferred_unavailable`,
  `model_unavailable_error`, `identity_propagated_to_trace` (ya de 6a),
  `admin_capability_no_identity_required`,
  `config_validate_detects_dangling_reference`.
- `eval.run` produce el formato del ADR 0017 con `conformance_digest` estable
  entre ejecuciones.
- `domain.route` por CLI devuelve dominio + modelo + motivo y lo registra en
  traza.
- La pista smoke queda lista para lanzarse contra el backend real (la dispara
  el usuario).
- `pytest` en verde, con tests de: ruteo por reglas, fallback,
  `ModelUnavailable`, `config.validate`.

## Restricciones y convenciones

- Python 3.13; pip + venv; pytest. Sin linter/type-checker.
- Identificadores y claves en ingles snake_case; prosa/comentarios en espanol
  sin tildes.
- Modulos pequenos, probables de forma aislada. Reutiliza lo de 6a
  (`adapters`, `telemetry`, `identity`, `registry`, `config`).
- El repo es PUBLICO: nada interno (IPs, hosts, secretos) en archivos
  versionados; endpoints/credenciales por variable de entorno.
- Corres en esta misma maquina: puedes leer `local/`. NO conectes al host de
  laboratorio; usa `FakeAdapter` para conformance. El smoke real lo lanzo yo.
- Si encuentras una ambiguedad o contradiccion en los docs, PARA y
  preguntame (puede ser trabajo en curso de otra IA).

## Entrega y handoff de vuelta

Rama nueva desde `main` (p.ej. `fase-6b-router-eval`), codigo + tests en
verde, y una nota breve de las decisiones que tomaste. Opus verifica: ejecuta
la bateria conformance completa, comprueba el `conformance_digest`
reproducible y revisa la traza de ruteo contra el ADR 0015.
