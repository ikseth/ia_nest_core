# Decision 0023: diseno del bucle de razonamiento (reasoning.run)

Fecha: 2026-07-11

## Decision

`reasoning.run` (sin herramientas, ADR 0022) se implementa como:

- Mecanismo: borrador y refinamiento. Iteracion 1 produce un borrador; las
  siguientes lo critican y refinan.
- Parada: el modelo senala cuando esta satisfecho (flag `done` estructurado);
  los limites de iteraciones, tiempo y presupuesto de tokens (ADR 0008)
  garantizan la terminacion. Motivo de parada tipado: `model_done` |
  `max_iterations` | `max_time` | `max_context_tokens`.
- Observabilidad: cada iteracion emite un evento `step` por el flujo D2
  (ADR 0004/0015) con `{iteration, output, done}`; el modo bloqueante colecta
  hasta `done`.
- Presupuesto de contexto: se lleva la cuenta y se PARA con motivo tipado al
  excederlo. La compactacion (resumen) y su enganche con la costura de memoria
  (ADR 0011) quedan diferidos.

## Motivo

Es la version minima, observable y controlable del bucle: cada paso es un
candidato completo (facil de observar), la parada combina criterio del modelo
con limites duros (terminacion garantizada), reutiliza la primitiva de
streaming existente, y respeta el presupuesto de contexto (ADR 0008) sin
construir compactacion/memoria que aun no tiene donde escribir (anti-entropia).

## Consecuencia

- `reasoning.run` se expone por CLI/REST/MCP via la capa de servicio
  (paridad, fase 7).
- Limites configurables por perfil (ADR 0014): `max_iterations`,
  `max_time_s`, `max_context_tokens` (ya en el esquema).
- "Desactivar pasos no necesarios" = configurable (p.ej. `max_iterations=1`
  produce solo el borrador, sin refinamiento).
- La compactacion se planificara cuando exista la memoria real (repo externo).
