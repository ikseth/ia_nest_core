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

## Senal de degeneracion mecanica de la generacion

Candidato registrado por ADR 0042, no construido. La FORMA de la salida puede
degenerar sin que el core entienda su significado: bucles de repeticion,
colapso de entropia. Es detectable mecanicamente -sin juicio semantico-, lo que
la hace hermana de `finish_reason` (senal de la generacion, no de su sentido).
El juicio de si una respuesta "tiene sentido" es semantico y NO es del core
(ADR 0025, conscience).

Evidencia (laboratorio 2026-08-07): deepseek-r1 entro en bucle "7.7.7..." hasta
agotar tokens. Frontera: mecanico (repeticion) = posible core; semantico
(coherencia, validez de un dato) = conscience.

No se construye sin consumidor real. El consumidor plausible existe -que
coverage rechace y reintente un fragmento degenerado- pero es capacidad nueva,
con su alcance y su bateria; se decide aparte (anti-entropia).

Antes de tratarlo como desarrollo, valorar si la respuesta es de CONFIGURACION,
no de codigo: la degeneracion observada puede ser especifica de un modelo
(deepseek-r1) y corregible por parametros del backend (p.ej. penalizacion de
repeticion, limite de generacion) o por eleccion de modelo por dominio, sin
tocar el core. El core solo aportaria la senal; actuar sobre ella es de las
capas o del operador.

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
