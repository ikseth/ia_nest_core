# Core contract

Estado: validado (2026-07-10)

## Proposito

Definir la frontera publica de IA_NEST Core.

El core debe enrutar, ejecutar y evaluar prompts usando modelos locales,
dominios y configuracion declarativa.

## Interfaces publicas

El core debe exponer las mismas capacidades por:

- CLI,
- API REST,
- MCP.

## Contexto de identidad del request

Las capacidades que participan en sesion, razonamiento o trazabilidad de
usuario (`prompt.run`, `reasoning.run`, `domain.route`) transportan un
contexto de identidad, aunque la memoria del core sea nula por defecto (ver
ADR 0011 y "Frontera de memoria" en `ARCHITECTURE.md`). Las capacidades
administrativas o de introspeccion (`runtime.health`, `model.list`,
`domain.list`, `config.validate`) NO lo requieren.

Campos:

- `user_id`
- `service` (ejemplos genericos: `local_cli`, `external_agent`,
  `integration_x`; el core no conoce nombres de modulos concretos)
- `session_id` (continuidad de sesion; opcional segun capacidad)
- `domain_tag`
- `namespace` (ejemplos: `facts`, `tasks`, `preferences`, `persona`, `ops`,
  `safety`)

Estos campos deben reflejarse en la traza (telemetria, ADR 0010).

Identidad por defecto: en uso local (CLI) existe una identidad local
CONFIGURADA por defecto (operador local con nombre), no un modo anonimo, de
modo que no haya que pasar identidad a mano en cada invocacion sin fragmentar
la continuidad de la entidad.

Motivo: si la identidad no viaja en el camino de inferencia desde el inicio,
incorporar memoria despues obliga a re-hilar identidad por todo el core. Se
incluye ahora aunque el core minimo no la use, para no crear deuda. Acotarla
a las capacidades de usuario/sesion evita rigidez innecesaria en las
administrativas.

## Capacidades minimas

### `runtime.health`

Informa del estado del runtime local.

Debe comprobar:

- proceso core,
- backend de modelos,
- disponibilidad basica de modelos,
- deteccion de GPU cuando aplique.

### `model.list`

Lista modelos conocidos y su estado.

Debe devolver:

- identificador,
- proveedor,
- disponibilidad,
- capacidades declaradas,
- perfil recomendado.

### `domain.list`

Lista dominios disponibles.

Debe devolver:

- identificador,
- descripcion corta,
- modelo preferido,
- politica de inferencia,
- estado.

### `domain.route`

Recibe un prompt y propone dominio, modelo y perfil.

Debe devolver:

- dominio seleccionado,
- confianza,
- motivo breve,
- alternativas relevantes.

### `prompt.run`

Ejecuta un prompt contra el dominio seleccionado o declarado.

Debe devolver:

- respuesta,
- modelo usado,
- dominio usado,
- parametros efectivos,
- trazabilidad minima.

### `reasoning.run`

Ejecuta razonamiento iterativo controlado.

Debe tener:

- limite de iteraciones,
- limite de tiempo,
- salida observable,
- capacidad de desactivar pasos no necesarios.

### `config.validate`

Valida configuracion declarativa.

Debe comprobar:

- modelos,
- dominios,
- perfiles,
- rutas,
- incompatibilidades basicas.

### `eval.run`

Ejecuta una bateria de evaluacion.

Debe devolver:

- resultados por caso,
- latencia,
- modelo usado,
- dominio usado,
- veredicto reproducible.

## No capacidades

El core no implementa:

- RAG,
- busqueda web,
- Home Assistant,
- consciencia,
- agentes autonomos,
- frontend completo.

Estas capacidades deben entrar por repos o modulos externos.

## Reglas de compatibilidad

- Toda capacidad publica debe tener contrato versionado.
- Toda capacidad publica debe poder probarse sin servicios externos complejos.
- La CLI debe ser la primera interfaz verificable.
- MCP y REST no deben tener logica distinta a la CLI.

