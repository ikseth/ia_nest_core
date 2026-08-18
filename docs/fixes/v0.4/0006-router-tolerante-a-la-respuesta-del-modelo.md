# 0006: el router semantico tira clasificaciones correctas por un campo decorativo

Estado: implementada (diagnostico CORREGIDO 2026-08-18)
Tipo: robustez del runtime (no toca contrato publico)
Impacto de version: patch
Version objetivo: v0.4.x

## Problema

Medido en laboratorio con modelos reales (mistral-nemo como router, cuatro
dominios de la plantilla `lab`, modelo ya caliente, 4 prompts x 3 intentos):

    codigo        3/3 correcto
    linux         3/3 correcto
    humanidades   1/3
    matematicas   1/3

Los fallos NO son clasificaciones erroneas: son
`reason: "router failed: RoutingError"` con `confidence: 0.0`, o sea que el
router se cae y `domain.route` degrada al dominio por defecto.

Lo que se descarto, con evidencia y no por intuicion:

- **No es arranque en frio.** Falla con el modelo cargado y caliente.
- **No es el parser rechazando respuestas buenas.** Reproducido el prompt exacto
  del core contra el modelo: las respuestas parsearon correctamente.
- **No es corrupcion al decodificar en el core.** `decode("utf-8")` se hace por
  LINEA del flujo SSE, y `\n` no aparece dentro de un caracter multibyte.
- **No es que clasifique mal.** Cuando responde, acierta con `confidence` 0.95.

## Correccion del diagnostico (2026-08-18)

**La primera version de esta ficha se equivocaba de causa, y conviene que conste.**

Decia que el modelo colaba caracteres multibyte malformados dentro de `reason` y
que eso rompia el JSON. La prueba en la que se apoyaba era una sola: una respuesta
buena en la que la palabra "operacion" llego con su acento convertido en dos
caracteres basura. Era un artefacto real, pero **inocuo**, y se construyo una
teoria encima.

Al medir de verdad, doce clasificaciones con el motivo de cada fallo:

    parsean: 7 de 12
    x5  confidence no numerica: 'high'

**Los cinco fallos son el mismo, y ninguno es de codificacion.** El modelo
responde:

    { "domain": "matematicas", "confidence": "high", "reason": "..." }

`confidence` llega como PALABRA. El parser exige `int` o `float`, devuelve `None`
y se descarta el objeto entero, con su `domain` correcto dentro.

Eso explica lo que la teoria anterior no explicaba: por que fallan unos dominios
y no otros -el modelo tiende a lo cualitativo en unos temas y a la cifra en
otros-, y por que un reintento no ayudaba: el modelo repite su forma, no juega a
los dados.

### Y la causa esta en lo que PEDIMOS, no en lo tolerantes que somos

La instruccion decia "Return only JSON with domain, confidence, reason" sin
declarar que `confidence` fuera un numero. Anadiendo una frase:

    confidence must be a NUMBER between 0 and 1, never a word.

    instruccion actual     ->   6 de 12 parsean
    instruccion explicita  ->  12 de 12

Medido con el mismo modelo, los mismos prompts y la misma tanda. La leccion, que
vale mas que el arreglo: **antes de hacer un parser mas tolerante, comprobar si
la peticion era ambigua.** Tolerar una respuesta que nunca deberia haber llegado
asi es tratar el sintoma.

## Por que la conformidad no lo veia

La bateria enruta contra un router guionizado que siempre devuelve un objeto
bien formado. Es correcto para fijar la semantica y no puede ver esto. Es el
mismo motivo por el que existen las fichas v0.3/0001 y v0.3/0002: parsers que
solo se rompen contra un modelo real.

## Cambio

Tres medidas. La primera es la que arregla el problema medido; las otras dos son
red de seguridad y siguen valiendo por si mismas.

### 1. Pedir el numero explicitamente

La instruccion de clasificacion declara que `confidence` es un numero entre 0 y 1
y nunca una palabra. Es la medida que lleva la tanda de 6/12 a 12/12.

### 2. `reason` deja de ser obligatorio

El parser acepta la respuesta con `domain` y `confidence`, y trata `reason` como
opcional. Cuando falte o no sea utilizable, el core publica una razon propia que
lo dice -algo como `router did not provide a reason`- en vez de descartar la
clasificacion entera.

`domain` y `confidence` siguen siendo obligatorios: son cortos, uno es un
identificador ASCII del catalogo y el otro un numero, asi que su probabilidad de
corromperse es despreciable comparada con la de una frase.

**El contrato no cambia**: `domain.route` sigue publicando `domain`,
`confidence`, `reason` y `alternatives`, con los mismos tipos. Lo que cambia es
de donde sale `reason` cuando el modelo no lo da.

### 3. Un reintento antes de degradar

Si la clasificacion falla, se reintenta UNA vez antes de caer al dominio por
defecto. La corrupcion es intermitente, asi que un reintento convierte un fallo
de 2 de cada 3 en algo mucho mas raro.

Un solo reintento, no una politica de reintentos: el router esta en el camino de
`task.run` por subtarea, y multiplicar latencia ahi se paga en cada tarea.

## Lo que NO se hace, y por que

- **No se relaja `domain`.** Si el modelo no dice a que dominio va, no hay
  clasificacion, y degradar al dominio por defecto es lo correcto.
- **No se acepta un identificador que no este en el catalogo.** Eso seria
  inventar un dominio.
- **No se cambia el prompt a "responde solo con el identificador".** Parece mas
  robusto y pierde `confidence`, que el contrato publica y que un consumidor
  puede usar para decidir si se fia. Es cambiar un problema por otro.
- **No se enruta con un modelo distinto del que responde.** Es configuracion del
  operador y ya se puede hacer hoy declarando otro `router.model`.

## Criterios de aceptacion

- Caso de conformidad: respuesta del router SIN `reason` -> se enruta igual, y la
  razon publicada dice que el router no la dio.
- Caso de conformidad: respuesta con `reason` que no es string -> mismo trato.
- Caso de conformidad: sin `domain`, o con un `domain` que no esta en el
  catalogo -> degradacion al dominio por defecto, como hoy.
- Caso de conformidad: el primer intento falla y el segundo acierta -> se enruta,
  con una sola repeticion y no mas.
- El digest de conformidad se mueve por los casos nuevos y se DECLARA.
- En laboratorio, la tanda de 4 prompts x 3 intentos mejora de forma medible.
  **Medido: 8/12 antes, 12/12 despues**, con los cuatro dominios correctos en los
  tres intentos.

## Archivos previstos

- `src/ianest_core/domain_router.py`
- `eval/battery/router/domain_route.yaml`, `eval/README.md`
- `CHANGELOG.md`

## No cubre

- La calidad de las descripciones de dominio, que es configuracion del operador
  (ADR 0043).
- El router como parte de `task.run` por subtarea: se beneficia de esto sin
  cambios propios.
- La eleccion del modelo de router, que es del operador.

## Resultado

Implementada. La instruccion pide el numero, `reason` es opcional con razon
propia del core, y hay un reintento antes de degradar. Laboratorio: **12 de 12**,
frente a 8 de 12 antes. Conformidad 125/125 con digest declarado.
