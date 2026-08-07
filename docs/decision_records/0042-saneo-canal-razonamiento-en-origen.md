# Decision 0042: el core separa el canal de razonamiento del de respuesta, en origen

Fecha: 2026-08-07
Estado: reconciliado por el usuario (2026-08-07)

## Decision

El canal de RESPUESTA de un modelo no es el canal de RAZONAMIENTO. El core los
separa en la frontera del adaptador, antes de que nadie use la respuesta.

### Principio

La respuesta que el core entrega -y que el validador juzga, el ensamblado
concatena y la telemetria graba- contiene solo el contenido de respuesta del
modelo. El razonamiento intermedio que algunos modelos emiten (familia R1 y
similares) no contamina ese canal: se separa y se conserva aparte.

### Donde: en el cuello, no en cada adaptador

El saneo vive en `run_blocking` (`adapters/base.py`), el punto por el que pasa
toda respuesta de modelo del camino bloqueante (`prompt.run`, `reasoning.run`,
`task.run` en sus dos modos). Es la frontera entre "cualquier runtime" y
"cualquier adaptador".

Consecuencia buscada: un adaptador nuevo emite tokens crudos y ya; NO construye
la respuesta final. No puede saltarse el saneo porque no es el quien lo hace.
Es enforcement estructural, no disciplina: la modularidad del core no queda a
merced de que cada adaptador futuro se acuerde.

La misma funcion pura de separacion se aplica en el colector de streaming de
`prompt_runtime.stream`, por consistencia. Los dos unicos puntos de llamada;
ningun adaptador toca ninguno.

### Como: dos mecanismos, con responsabilidad distinta

El razonamiento llega de dos formas segun el backend, y se tratan en capas
distintas a proposito:

1. **Inline** (`<think>...</think>` dentro del contenido). Es lo que hoy emite
   Ollama con deepseek-r1. Si no se retira, CONTAMINA la respuesta. Por eso su
   retirada va en `run_blocking` (el cuello, obligatorio): prevenir la fuga no
   puede depender de un adaptador.

   Un `<think>` ABIERTO SIN CERRAR cuenta como razonamiento hasta el final del
   texto. Ocurre cuando el modelo agota su presupuesto de tokens antes de
   cerrar la etiqueta (`finish_reason=length`): el canal de razonamiento se
   abrio y nunca volvio al de respuesta. La respuesta limpia es lo anterior al
   `<think>` (a menudo, vacia), y ese vacio con `finish_reason=length` es la
   salida honesta -el modelo no llego a responder-. Verificado en laboratorio
   el 2026-08-07 (puerta A.2): sin esto, un razonamiento truncado de 4405
   caracteres se filtraba entero como respuesta.

2. **Campo aparte** (`reasoning_content` / `reasoning`, separado del contenido).
   Es la via a la que tiende el ecosistema. Solo el adaptador ve el cable, asi
   que es el adaptador quien lo captura y lo pasa en el evento `done`. Si un
   adaptador futuro lo omite, el razonamiento simplemente no se enruta a
   telemetria: se pierde, pero NO se filtra. Degradacion graciosa, no fuga.

El nombre del campo aun no esta estandarizado; es un detalle interno del
adaptador (no contrato publico), barato de ajustar cuando el ecosistema se
asiente.

### Rutear, no borrar

El razonamiento separado no se descarta: se conserva en la telemetria JSONL
(nunca en CSV; es contenido, ADR 0010/0015). El canal de razonamiento es una
senal valiosa para las capas de observacion (pulse, conscience); enlaza con el
precedente de `finish_reason` como senal del core (ficha v0.2/0002,
`CAPAS_FUTURAS.md`).

`ModelResponse` gana un campo `reasoning` (string, por defecto vacio), aditivo.

## Lo que esta decision NO hace

Sanea la FORMA, no juzga el FONDO. La frontera es mecanico vs semantico, no
factibilidad vs sentido:

- Retirar `<think>` es mecanico: es sintaxis conocida. Core.
- Saber que `160.0.2.4.0.0` no es una IP, o que un texto carece de coherencia
  linguistica, es juicio semantico: pide un modelo con criterio propio. No es
  del core (ADR 0025, verificacion de respuesta asignada a conscience). Ademas,
  la evidencia de laboratorio muestra que pedirselo al mismo 7B que fallo no da
  verdad: el validador de coverage acepto la basura que genero deepseek.

Registrado como concern candidato, FUERA de esta linea (decision del usuario,
2026-08-07):

- **Senal de degeneracion mecanica** (bucles de repeticion, colapso de
  entropia): detectable sin entender significado, hermana de `finish_reason`.
  Podria ser core el dia que tenga consumidor real (p.ej. que coverage rechace
  y reintente un fragmento degenerado). No se construye sin ese caso
  (anti-entropia, leccion MemoryPort). Vive en `CAPAS_FUTURAS.md`.
- **Juicio de adecuacion/coherencia semantica**: conscience (ADR 0025).

## Motivo

Evidencia de laboratorio (2026-08-07, detalle en `local/lab/`): una tarea de
red enruto una subtarea a deepseek-r1, que emitio `<think></think>` seguido de
texto degenerado. Tres cosas pasaron encadenadas:

1. las etiquetas `<think>` viajaron crudas hasta la respuesta final;
2. el validador de coverage -otro modelo- las dio por buenas: `coverage_complete
   = true` sobre ruido;
3. si ese modelo hubiera sido el planner o el evaluator, el `<think>` habria
   roto el parseo de su JSON; en `reasoning.run` rompe el `json.loads` y degrada
   a `done: false`.

Sanear al FINAL (en un modulo de render o parsing de salida) no evita nada de
esto: el validador ya juzgo basura, la telemetria ya la grabo, la cobertura ya
miente. Sanear en ORIGEN hace que todo aguas abajo -validador, parsers de
orquestacion, ensamblado, telemetria- vea texto limpio. Un solo punto protege a
todos.

No es ad-hoc por modelo: la clave es la CONVENCION (`<think>`, campo de
razonamiento), no el id del modelo. Si el usuario cambia deepseek por otro
razonador, sigue valiendo; si el nuevo modelo no razona en banda, es un no-op.
No hay colision posible.

Pasa el tamiz de diseno del usuario (resiliencia, escalabilidad, modularidad,
sencillez, estrategia): cimiento correcto (el core normaliza su frontera),
una funcion pura en un cuello que ya existe, heredada por cualquier adaptador
futuro, sin modulo nuevo ni logica por modelo.

## Consecuencia

- `ModelResponse` gana `reasoning: str = ""` (aditivo).
- `run_blocking` y el colector de streaming aplican `split_reasoning`;
  `OpenAICompatibleAdapter` captura el campo de razonamiento del cable si viene.
- `prompt_runtime` graba `reasoning` en el payload JSONL; nunca en CSV.
- Contrato: `CORE_CONTRACT.md` no lista el contenido interno de `response`, pero
  se anade una nota: la respuesta excluye el canal de razonamiento del modelo.
- Impacto de version: PATCH. Campo aditivo y correccion de un defecto observable
  (razonamiento filtrado en la respuesta). El numero lo corta el usuario.
- Digest de conformance: SIN CAMBIO. Los fakes no emiten razonamiento; el saneo
  es no-op sobre ellos. Se verifica que el digest `5aa67516...` no se mueve.
- Tests (por no ser expresables end-to-end con fakes reales):
  - `split_reasoning` como funcion pura: retira `<think>...</think>` (incluido
    multilinea y varias apariciones), retira un `<think>` sin cerrar desde la
    etiqueta hasta el final, respeta texto sin marcas, y devuelve el
    razonamiento separado;
  - un `FakeAdapter` al que se le inyecta `<think>` en la respuesta sale limpio
    por `run_blocking` y su razonamiento aparece en la traza JSONL;
  - el campo de razonamiento del cable, cuando el adaptador lo captura, tambien
    se enruta a JSONL y no al contenido.
- Puerta de laboratorio (fase A): la subtarea que toca un modelo razonador deja
  de mostrar `<think>` en la respuesta, y el razonamiento aparece en el JSONL.
- Encaje: fase A (saneo de salida), junto a las fichas v0.3/0004 y 0005.
- Alternativas descartadas:
  - **Sanear en un modulo de parsing/render de salida**: llega tarde; el
    validador y la telemetria ya vieron la basura.
  - **Sanear dentro de cada adaptador**: correcto conceptualmente (es el origen)
    pero olvidable; un adaptador futuro reabriria la fuga. El cuello lo hace
    inolvidable.
  - **Borrar el razonamiento en vez de rutearlo**: tira una senal que pulse y
    conscience querran. Cuesta lo mismo conservarla.
  - **Solo el inline, ignorar el campo**: deja sin enrutar el razonamiento de
    los backends que ya lo separan. El campo cuesta casi nada y cubre el core
    que va a crecer.
  - **Juzgar la coherencia de la respuesta con un modelo**: revierte ADR 0025 y,
    con evidencia, pide al modelo que fallo que se autodetecte.
