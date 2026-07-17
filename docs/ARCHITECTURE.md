# Arquitectura

Estado: validado (usuario 2026-07-10, auditoria cruzada con Codex reconciliada)
Version: 0.8 - 2026-07-10
Autor de la propuesta: Claude Code (Opus), rol disenador
Decisiones promovidas a ADR: D1->0003, D2->0004, D3->0005, D4->0006,
D5->0007, D6->0008, D7->0009, D8->0010, frontera de memoria->0011.

Este documento resuelve los riesgos abiertos en el ADR 0002 y define la
arquitectura minima del core. Validado por el usuario el 2026-07-10, tras
reconciliar la auditoria cruzada de Codex.

## Vision de conjunto

Un request entra por una de las tres interfaces (CLI, REST, MCP), que son
finas y no tienen logica propia (regla de `CORE_CONTRACT.md`). Todas llaman
al mismo nucleo:

```
  CLI ─┐
  REST ─┼─> capa de interfaz (fina) ─> nucleo
  MCP ─┘

  nucleo:
    domain_router ──> model_registry ──> prompt_runtime ──> adapter ─> backend local
         │                                     │
         └──> reasoning_loop ──────────────────┘
                    │
    telemetry <── (todos emiten trazas) ──> evaluation
    tool_contracts (invocado por reasoning_loop bajo politica)
```

Regla transversal: cada componente se explica en una pagina y se prueba de
forma aislada con dobles de prueba (fakes) para sus dependencias.

## Decisiones de diseno propuestas

D1-D6 resuelven el ADR 0002. D7-D8 provienen del feedback del usuario del
2026-07-10. Validadas y promovidas a los ADRs 0003-0010 (y 0011 para la
frontera de memoria).

### D1. Protocolo de cable del runtime: OpenAI-compatible como diana

`prompt_runtime` no habla con los backends directamente: habla con una
interfaz `ModelAdapter`. El adaptador por defecto habla el dialecto
OpenAI-compatible (Chat Completions), porque Ollama, llama.cpp (server) y
vLLM ya lo exponen. Un backend nuevo se soporta escribiendo un adaptador,
no tocando el runtime.

Motivo: sirve sobre todo al control local (prioridad 3 de
`VISION_FUNCIONAL.md`) y, al permitir elegir el mejor backend local por
dominio, tambien a calidad y rendimiento (prioridades 1 y 2). La facilidad
de cambio de modelos (prioridad 4) es una consecuencia, no la justificacion
principal. No acopla el core a un proveedor concreto.

Coste asumido: el dialecto OpenAI no cubre todo (algunos parametros de
sampling propios de un backend quedan fuera del contrato comun y se pasan
como `extra` opaco).

### D2. Streaming como primitiva; bloqueante como conveniencia

El contrato interno de ejecucion emite un flujo de eventos
(`token`, `step`, `trace`, `done`, `error`). La variante bloqueante
(`prompt.run` que devuelve texto completo) es un consumidor que colecta el
flujo hasta `done`. Asi el contrato es uno solo y no se rompe al anadir
streaming despues.

En CLI/REST/MCP: el modo bloqueante es el que colecta; el modo streaming
expone el flujo (SSE en REST, chunks en CLI, streaming de MCP donde aplique).

### D3. Politica de fallo ante modelo no disponible: cadena declarada + error tipado

Cada dominio declara `modelo_preferido` y una lista opcional
`modelos_alternativos`. Si el preferido no esta disponible (segun
`runtime.health` / registry), el router intenta la lista en orden. Si
ninguno esta disponible, devuelve un error tipado
`ModelUnavailable` con el detalle, nunca un fallback silencioso a un modelo
no declarado. La sustitucion efectiva se registra en la traza del request.

Motivo: preserva trazabilidad (principio 5) y evita sorpresas de calidad.

### D7. Adoptar antes que construir (infraestructura estandar)

No se desarrolla lo que ya existe como estandar open-source maduro. Para
piezas de infraestructura (servidor MCP, framework API/REST, backends de
modelos, contenedores) se adopta una solucion existente y el core aporta:
configuracion declarativa, scripts de instalacion/personalizacion y
documentacion. Se construye solo el valor diferencial: orquestacion,
dominios, evaluacion y las fronteras del core.

Heuristica adoptar vs construir: se adopta si (a) es un estandar con varias
implementaciones, (b) no exige fork ni mantenimiento pesado, y (c) se puede
envolver tras un contrato fino propio (patron adaptador, como en D1) para
no quedar acoplados. Se construye solo si el componente ES el valor
diferencial del core.

Candidatos concretos: SDK oficial MCP (no implementar el protocolo);
framework API estandar para REST; Ollama/llama.cpp/vLLM como backends (ya
en D1); imagenes de contenedor existentes (no desarrollar contenedores).

Nota: por ser transversal, esta decision puede promoverse ademas a
principio en `IA_NEST_CORE_CONTEXT.md` / `CONVENCIONES.md`.

### D8. Formato de telemetria: CSV clasico + JSONL para contenido, sin sqlite

Decision del usuario (2026-07-10, refinada tras auditoria): nada de sqlite.
Dos sinks de formato fijo y documentado:

- CSV para telemetria clasica tabular: latencia, tokens, modelo, dominio,
  veredicto, identidad, timestamps. Delimitador ";". Rotacion por tamano
  y/o fecha. Esquema (orden y nombres de columna) congelado y versionado.
  El CSV NO contiene cuerpos de prompt ni de respuesta.
- JSONL (un objeto JSON por linea) para todo lo que involucre contenido de
  prompt o respuesta, y para eventos estructurados o anidados. El texto
  libre vive siempre aqui, nunca en el CSV.

Como el texto libre no entra en el CSV, se evita de raiz el problema de
delimitadores y saltos de linea en campos ";". Aun asi, para cualquier campo
CSV se usa la libreria CSV estandar del lenguaje, no un parser propio.

Regla de resiliencia: un fallo de telemetria NO debe romper la inferencia.
La escritura es best-effort y se degrada en silencio (dejando su propio
registro de error), salvo un modo estricto opt-in en el que si detiene la
operacion.

Motivo: formato estandar, legible, rotable, sin motor de base de datos; la
observabilidad no compromete la funcion principal.

### D4. Version de protocolo MCP: declarada y verificable

El core declara una version objetivo del protocolo MCP en `runtime.health` y
la hace verificable (un cliente puede comprobar contra que version habla).
Se soporta salida estructurada de herramientas. El numero de version
concreto se elige al implementar la interfaz MCP, tras verificar la revision
estable vigente entonces (no antes, para no anclar una version que quede
obsoleta en el borrador). El compromiso es que exista una version declarada
y verificable, no que el numero este ya elegido.

### D5. Modelo de confianza de `tool_contracts`: denegar por defecto

Ninguna herramienta tiene acceso implicito a shell, filesystem o red. Cada
herramienta declara capacidades y ambito (scopes) explicitos; el core
aplica allowlist. Toda operacion marcada como destructiva o irreversible
exige confirmacion humana (human-in-the-loop) y no puede ejecutarse en modo
desatendido.

Motivo: traduce el no-objetivo "no automatizacion Linux destructiva" a una
regla tecnica exigible, y mitiga tool poisoning / confused deputy conocidos
en el ecosistema MCP.

### D6. Presupuesto de contexto: coherencia y estabilidad de la entidad, no coste

Correccion (feedback 2026-07-10): en un core que simula un "ente", el
presupuesto de contexto/tokens NO es una cuestion de coste/pago (los
modelos son locales, no hay factura por token) sino de rendimiento y
estabilidad de la entidad. El limite existe para que la entidad se
mantenga coherente y no degrade su razonamiento al saturar o desbordar la
ventana.

`reasoning_loop` trata la ventana de contexto como recurso cognitivo
limitado, junto a los limites de iteraciones y tiempo. Al acercarse al
limite, para o compacta (resumen) segun politica declarada, y lo registra
en la traza. Nunca desborda la ventana de forma silenciosa.

Vinculo con memoria: lo que cae fuera del contexto de trabajo (por
compactacion o por limite) es el candidato natural a persistir en memoria.
D6 y la frontera de memoria son la misma costura vista desde dos lados
(ver seccion "Frontera de memoria").

## Componentes

Orden de dependencia: `telemetry` y `model_registry` son base;
`domain_router` depende del registry; `prompt_runtime` depende de registry
y adaptadores; `reasoning_loop` depende de runtime y (bajo politica) de
tool_contracts; `evaluation` depende de todo lo anterior a traves de sus
contratos.

### model_registry

- Responsabilidad: catalogo declarativo de modelos y su estado de
  disponibilidad. Fuente de verdad de que modelos existen y cuales estan
  usables ahora.
- Entradas: configuracion declarativa (JSON/YAML) de modelos; consultas de
  disponibilidad al backend/adaptador.
- Salidas: `model.list` (identificador, proveedor, disponibilidad,
  capacidades declaradas, perfil recomendado).
- Estado interno: catalogo cargado + cache de disponibilidad con TTL.
- Dependencias: `ModelAdapter` (para probar disponibilidad), `telemetry`.
- Decisiones que aplica: D1, D3.
- Prueba aislada: con un adaptador fake que reporta disponibilidad
  controlada; se verifica listado, capacidades y transicion
  disponible/no-disponible.

### domain_router

- Responsabilidad: dado un prompt, proponer dominio, modelo y perfil;
  aplicar la cadena de fallo D3.
- Entradas: prompt; catalogo de dominios (declarativo); estado del registry.
- Salidas: `domain.list`, `domain.route` (dominio, confianza, motivo
  breve, alternativas).
- Estado interno: perfiles de dominio cargados; politica de enrutado.
- Dependencias: `model_registry`, `telemetry`.
- Decisiones que aplica: D3.
- Prueba aislada: con registry fake y catalogo de dominios de prueba; se
  verifica ruteo por reglas, motivo y comportamiento de fallback.
- Nota: la primera version puede rutear por reglas declarativas (palabras
  clave/etiquetas) antes de introducir ruteo por modelo. No se asume
  clasificador entrenado en el core minimo.

### prompt_runtime

- Responsabilidad: ejecutar un prompt contra un modelo via adaptador,
  emitiendo el flujo de eventos D2.
- Entradas: prompt + dominio/modelo resuelto + parametros efectivos.
- Salidas: `prompt.run` (respuesta, modelo usado, dominio usado, parametros
  efectivos, trazabilidad minima); flujo de eventos en modo streaming.
- Estado interno: minimo; es sobre todo orquestacion sin estado por request.
- Dependencias: `ModelAdapter` (D1), `model_registry`, `telemetry`.
- Decisiones que aplica: D1, D2.
- Prueba aislada: con adaptador fake que emite un flujo conocido; se
  verifica coleccion bloqueante, streaming y campos de trazabilidad.

### reasoning_loop

- Responsabilidad: razonamiento iterativo controlado y observable, con
  limites de iteraciones, tiempo y presupuesto de tokens (D6); puede
  invocar herramientas bajo politica (D5).
- Entradas: objetivo/prompt; limites; pasos habilitados/deshabilitados.
- Salidas: `reasoning.run` (salida observable por paso; flujo D2).
- Estado interno: estado del bucle por request (iteracion, presupuesto
  consumido); no persistente.
- Dependencias: `prompt_runtime`, `tool_contracts` (opcional, bajo
  politica), `telemetry`.
- Decisiones que aplica: D2, D5, D6.
- Prueba aislada: con runtime fake; se verifica corte por cada limite
  (iteraciones, tiempo, tokens), desactivacion de pasos y observabilidad.

### tool_contracts

- Responsabilidad: contrato y frontera de confianza para herramientas
  externas invocables desde el core (D5).
- Entradas: declaracion de herramienta (capacidades, scopes,
  destructiva si/no); invocacion desde `reasoning_loop`.
- Salidas: resultado tipado de la herramienta o error de politica.
- Estado interno: allowlist y politica activa.
- Dependencias: `telemetry`.
- Decisiones que aplica: D5.
- Prueba aislada: con herramientas fake; se verifica denegar-por-defecto,
  respeto de scopes y bloqueo/confirmacion de operaciones destructivas.
- Frontera: el core invoca la herramienta por contrato; no absorbe su
  logica interna (regla de `ALCANCE_CORE.md`).

### evaluation

- Responsabilidad: ejecutar baterias de evaluacion reproducibles.
- Entradas: bateria de casos declarativa; configuracion de modelos/dominios.
- Salidas: `eval.run` (resultados por caso, latencia, modelo usado, dominio
  usado, veredicto reproducible).
- Estado interno: ninguno persistente; resultados se emiten/almacenan fuera.
- Dependencias: `prompt_runtime`, `domain_router`, `telemetry`.
- Decisiones que aplica: consume D1-D3.
- Prueba aislada: con runtime fake determinista; se verifica
  reproducibilidad del veredicto y estabilidad de metricas.

### telemetry

- Responsabilidad: trazabilidad por request y observabilidad; recibe
  eventos de todos los componentes.
- Entradas: eventos de traza (`trace`, `step`, `done`, `error`) con id de
  request.
- Salidas: traza consultable por request; base para el campo de
  trazabilidad minima de los contratos.
- Estado interno: buffer + sinks CSV/JSONL con rotacion (D8).
- Dependencias: ninguna (es base).
- Decisiones que aplica: D8; transversal a D2, D3, D6 (registra
  sustituciones, cortes y presupuesto).
- Prueba aislada: se inyecta como coleccionable en memoria; se verifica que
  cada request produce una traza correlacionada por id.

## Frontera de memoria

Estado: validado (ADR 0035, supersede parcialmente ADR 0011).
El core NO implementa memoria ni define un punto de conexion para ella. La
estrategia y la ejecucion de memoria viven en `ia_nest_extended`, que
enriquece el prompt antes de llamar al core y realiza el write-back con la
respuesta. El runtime del core no conoce la memoria.

### Identidad de segmentacion (clave aportada por el core)

La identidad de segmentacion debe viajar en el contexto de request/traza
para que extended pueda usarla como clave de memoria sin re-hilar identidad
por el core. Campos:

- `user_id`
- `service` (ha, nextcloud, linux, chat, global...)
- `session_id` (solo tiers inmediatos)
- `domain_tag`
- `namespace` (facts, tasks, preferences, persona, ops, safety...)

Estos campos deben incluirse tambien en las trazas de telemetria (D8), para
que traza y memoria compartan identidad.

### Responsabilidades de extended

- Niveles concretos (immediate/short/medium/long/historical/principles).
- Pipeline de consolidacion por hitos.
- Doble conciencia (pertenece a `ia_nest_core_conscience`, no al core).
- Recuperacion semantica / RAG (pertenece a `ia_nest_extended`).
- Esquema SQL o motor de almacenamiento.

## Correspondencia con el contrato

- `runtime.health` -> model_registry + adaptadores + deteccion GPU + version MCP (D4).
- `model.list` -> model_registry.
- `domain.list`, `domain.route` -> domain_router.
- `prompt.run` -> prompt_runtime.
- `reasoning.run` -> reasoning_loop.
- `config.validate` -> validador declarativo (transversal; valida modelos,
  dominios, perfiles, rutas antes de arrancar).
- `eval.run` -> evaluation.

## Que queda fuera de esta arquitectura

- La version MCP concreta (D4) se fija al implementar la interfaz MCP.
- El esquema de `config.validate` esta fijado en el ADR 0014; su pagina de
  detalle puede escribirse al implementar.
- La estrategia y ejecucion de memoria (niveles, consolidacion): viven en
  `ia_nest_extended`; el core solo aporta la identidad como clave (ver
  "Frontera de memoria").
