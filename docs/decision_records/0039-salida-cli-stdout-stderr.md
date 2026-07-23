# Decision 0039: salida CLI - stdout es la respuesta, stderr es el progreso

Fecha: 2026-07-23
Estado: propuesta (pendiente de reconciliacion del usuario)

## Decision

La CLI separa su salida por flujo, de forma UNIFORME para todas las
capacidades que emiten flujo de eventos D2 (`prompt.run`, `reasoning.run`,
`task.run`):

- **stdout = la respuesta (los datos)**: el texto de la respuesta y, en
  streaming, los fragmentos en orden (`token` en prompt/reasoning,
  `answer_chunk` en coverage). Nada mas.
- **stderr = el progreso (la meta)**: una linea concisa y legible por cada
  hito relevante (plan listo, cobertura N/M, combinando, corte), para que
  el humano vea el avance en pantalla sin contaminar stdout.
- **`--json` (existente)**: emite los eventos estructurados completos a
  stdout, para consumo de maquina y depuracion. No cambia.
- **`--quiet` (nuevo)**: suprime tambien el progreso de stderr (silencio
  total salvo la respuesta en stdout, o los eventos en `--json`).

Regla para capacidades futuras: toda capacidad nueva de la CLI que emita
flujo se ajusta a este modelo.

## Motivo

Convencion UNIX (stdout=datos, stderr=meta): permite a la vez `capacidad
... > fichero` limpio (solo la respuesta) y ver el progreso en pantalla,
sin flag y sin sorpresas. Un flag `--progress` apagado por defecto dejaria
sin visibilidad justo cuando mas se quiere (depuracion); stderr la da
gratis y no ensucia el pipe. La depuracion estructurada ya la cubre
`--json`.

Es la contraparte por-interfaz del flujo de eventos como primitiva
(ADR 0004): el stream es uno, cada interfaz lo renderiza a su manera (REST
SSE, MCP streaming, CLI stdout/stderr). Esta decision fija el render de la
CLI.

Ademas resuelve por construccion el doble-texto observado en el modo
coverage (la respuesta se imprimia como fragmentos en streaming y otra vez
al cierre): al separar answer (stdout) de progreso (stderr), el cierre deja
de reimprimir.

## Alcance y no-alcance

- Afecta SOLO al render de la CLI. REST (SSE) y MCP ya separan transporte y
  no cambian.
- No cambia el contenido de la telemetria (ADR 0010/0015) ni los tipos de
  evento D2 (ADR 0004); es como la CLI los PRESENTA.

## Consecuencia

- La salida CLI de las tres capacidades se alinea a este modelo; el
  progreso deja de imprimirse en stdout como nombres de checkpoint crudos.
- Nueva bandera `--quiet` (aditiva, compatible); `--json` sin cambios.
- El doble-texto del modo coverage queda resuelto.
- Impacto de version: patch (mejora compatible: stdout se limpia, stderr y
  `--quiet` son aditivos; el progreso en stdout no era contrato declarado).
  El numero final lo fija el usuario en la reconciliacion; se integra en
  v0.3.0, aun sin cortar.
- Alternativas descartadas: bandera `--progress` apagada por defecto
  (pierde visibilidad por defecto, hay que recordarla para depurar);
  mantener progreso y respuesta en stdout (mezcla datos y meta, rompe
  pipes, causa el doble-texto).
