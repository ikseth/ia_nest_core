# Capas futuras (lo que el core debe a otras capas)

Registro de necesidades que NO pertenecen a `ia_nest_core` (por alcance /
anti-entropia) y de lo que el core SI tendra que aportar para que otra capa las
resuelva. Ver la costura de cada capa en `docs/FRONTERAS.md`.

Reparto (meta ADR 0004): el registro de quien existe y quien depende de quien
vive en `ia_nest_meta/docs/REGISTRO_CAPAS.md`; los concerns del ente SIN repo
asignado, en `ia_nest_meta/docs/CAPAS_FUTURAS.md`. Aqui queda el backlog del
motor. Donde el texto describe el diseno INTERNO de una capa aun no sembrada, va
marcado `[doctrina de capa]`: mudara a su repo cuando se siembre.

## pulse: lo que el core le debe

`[doctrina de capa]` Definido en ADR 0037. Motor de monitorizacion headless
(CPU/RAM) que observa la telemetria de todos los componentes y REGULA parametros
tecnicos dentro de los techos del core, subordinado a conscience. Sub-modos:
homeostasis continua y (futuro) respuesta por disparadores.

- Lo que SI hara el core: exponer el **dato** (readiness GPU en `runtime
  health`/`detect`) y las **senales** que pulse necesita, entre ellas
  `finish_reason` (truncado vs parada natural) por llamada/subtarea -senal
  foundational, hoy inexistente (el adaptador la ignora); se implementara como
  ficha de core-.
- Lo que NO hara el core: el bucle de vigilancia/regulacion continuo. Eso es
  pulse (`ia_nest_core_pulse`).
- `[doctrina de capa]` Primera responsabilidad de pulse (futura): presupuesto
  dinamico de tokens por dominio a partir del historico de truncados. No se
  construye sin la senal ni sin uso (leccion MemoryPort). Vigilancia del backend
  (p.ej. GPU caida tras `systemctl daemon-reload`, ADR 0028) tambien cae aqui.

## Voz del ente (combiner) y personalidad

Regla del core. El combiner de `task.run` (o el modelo unico en `prompt.run`)
produce la forma final: maqueta, traduce y da tono. Es la VOZ del ente, pero la
APLICA, no la CONTIENE: la personalidad se sedimenta en conscience (ADR 0034) y
se entrega via `system` prompt (ADR 0025) + enriquecimiento (extended). No
hardcodear personalidad en el combiner.

## conscience: lo que el core le debe

`[doctrina de capa]` Definida en ADR 0034. Supervisor que puede
bloquear/replantear en caliente (modo live, sobre checkpoints del orquestador
v0.2) y que en modo sueno hace quiesce del core y revisa la telemetria del dia
(JSONL/CSV) para aprender y generar nuevas tramas de memoria. Sedimenta sus
resoluciones (debates eticos y de personalidad) como memoria de comportamiento
en `extended`. Incluye el modelo de control/verificacion de respuesta (ADR 0025,
alternativa descartada para el core). Pertenece a `ia_nest_core_conscience`.

Lo que el core tendra que aportar (linea v0.2, cada una con su ADR):
checkpoints de supervision en el orquestador y capacidad administrativa de
quiesce.

## Memoria avanzada

Resuelto: vive en `ia_nest_extended`, que ya existe. La estrategia Y la
ejecucion son suyas (via 2, ADR 0031/0034) y se documentan en su repo; el core
solo aporta la identidad de segmentacion como clave. `MemoryPort` (ADR 0011)
queda superado; retirada pendiente junto al cambio de codigo.

## Otros

El mapa de que concern resuelve cada repo (RAG y busqueda web -> `extended`,
integraciones -> `external_*`, agentes -> `agents`) vive en el registro de capas
del ente: `ia_nest_meta/docs/REGISTRO_CAPAS.md`.

La comunicacion entidad-a-entidad (ADR 0033) es un concern del ente sin repo
asignado: se registra en `ia_nest_meta/docs/CAPAS_FUTURAS.md`.
