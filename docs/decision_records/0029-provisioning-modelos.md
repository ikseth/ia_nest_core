# Decision 0029: provisioning de modelos (capacidad opcional del backend)

Fecha: 2026-07-15

## Decision

El core puede asegurar que los modelos declarados en la config esten presentes
en el backend (descargarlos si faltan), como capacidad OPCIONAL y especifica
del backend, sin acoplar la inferencia:

- Interfaz `Provisioner` (opcional): `list_local() -> set[str]` y
  `pull(model_name)`.
- `OllamaProvisioner`: usa la API NATIVA de Ollama (`<base>/api/tags`,
  `<base>/api/pull`), derivando `<base>` del `endpoint` del modelo (quitando
  el sufijo `/v1`). Funciona por HTTP (Ollama local, en Docker o remoto).
- El core selecciona el provisioner por el `provider` del modelo; si el backend
  no tiene provisioner, la operacion informa "no soportado" (no rompe nada).
- Comando CLI `ianest model pull [MODEL...]`: sin argumentos, descarga los
  modelos DECLARADOS en la config que falten; con argumentos, descarga esos.

## Motivo

"Local y completo": el core vela por que sus recursos declarados esten listos,
evitando el paso manual de `ollama pull` (fuente de errores, visto en el
dogfooding). La inferencia sigue siendo agnostica (OpenAI-compatible, ADR 0003);
el provisioning es una capacidad aparte, opcional y backend-especifica -no toca
el `ModelAdapter` (ADR 0018)-.

## Consecuencia

- Nuevo modulo de provisioning (`Provisioner` + `OllamaProvisioner`) y
  subcomando `model pull`. `model.list` puede indicar presente-vs-declarado.
- Reutilizable por `deploy/setup.sh` (en vez de `docker exec ... ollama pull`).
- Backends sin provisioner: `model pull` informa que no esta soportado.
