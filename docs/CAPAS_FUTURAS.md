# Capas futuras (concerns fuera del core)

Registro de necesidades que NO pertenecen a `ia_nest_core` (por alcance /
anti-entropia) y que se resolveran en capas o repos externos. Se documentan
aqui para no perderlas y para alimentar la fase 10 (fronteras hacia repos
externos). Ver el mapa de repos en `IA_NEST_CORE_CONTEXT.md`.

## pulse: sistema nervioso autonomo del ente (monitorizacion + regulacion)

Definido en ADR 0037. Motor de monitorizacion headless (CPU/RAM) que observa la
telemetria de todos los componentes y REGULA parametros tecnicos dentro de los
techos del core, subordinado a conscience. Sub-modos: homeostasis continua y
(futuro) respuesta por disparadores.

- Lo que SI hara el core: exponer el **dato** (readiness GPU en `runtime
  health`/`detect`) y las **senales** que pulse necesita, entre ellas
  `finish_reason` (truncado vs parada natural) por llamada/subtarea -senal
  foundational, hoy inexistente (el adaptador la ignora); se implementara como
  ficha de core-.
- Lo que NO hara el core: el bucle de vigilancia/regulacion continuo. Eso es
  pulse (`ia_nest_core_pulse`).
- Primera responsabilidad de pulse (futura): presupuesto dinamico de tokens por
  dominio a partir del historico de truncados. No se construye sin la senal ni
  sin uso (leccion MemoryPort). Vigilancia del backend (p.ej. GPU caida tras
  `systemctl daemon-reload`, ADR 0028) tambien cae aqui.

## Voz del ente (combiner) y personalidad

El combiner de `task.run` (o el modelo unico en `prompt.run`) produce la forma
final: maqueta, traduce y da tono. Es la VOZ del ente, pero la APLICA, no la
CONTIENE: la personalidad se sedimenta en conscience (ADR 0034) y se entrega via
`system` prompt (ADR 0025) + enriquecimiento (extended). No hardcodear
personalidad en el combiner.

## Conscience: supervisor etico/de personalidad (dual live/sueno)

Definida en ADR 0034. Supervisor que puede bloquear/replantear en caliente
(modo live, sobre checkpoints del orquestador v0.2) y que en modo sueno hace
quiesce del core y revisa la telemetria del dia (JSONL/CSV) para aprender y
generar nuevas tramas de memoria. Sedimenta sus resoluciones (debates eticos y
de personalidad) como memoria de comportamiento en `extended`. Incluye el
modelo de control/verificacion de respuesta (ADR 0025, alternativa descartada
para el core). Pertenece a `ia_nest_core_conscience`.

Necesitara del core (linea v0.2, cada una con su ADR): checkpoints de
supervision en el orquestador y capacidad administrativa de quiesce.

## Memoria avanzada

Estrategia de memoria (niveles, consolidacion, memoria de comportamiento de
conscience). Via 2 (ADR 0031/0034): la estrategia Y la ejecucion viven en
`ia_nest_core_extended`; el core aporta la identidad de segmentacion como
clave. `MemoryPort` (ADR 0011) queda superado; retirada pendiente junto al
cambio de codigo.

## Comunicacion entidad-a-entidad

Varios entes IA_NEST comunicandose entre si (ADR 0033). Frontera futura del
ente; sin diseno asignado. Se registra para no perderla.

## Otros (mapa de repos)

- RAG, busqueda web -> `ia_nest_core_extended`.
- Integraciones (Home Assistant, Nextcloud) -> `ia_nest_external_*`.
- Agentes -> `ia_nest_agents`.
