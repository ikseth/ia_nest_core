# 0006: el router semantico tira clasificaciones correctas por un campo decorativo

Estado: propuesta
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

Lo que apunta a la causa: en una de las respuestas buenas, la palabra
"operacion" llego al campo `reason` con su acento convertido en dos caracteres
basura. Es el MODELO emitiendo caracteres multibyte malformados, cosa que un
modelo cuantizado hace de vez en cuando. Si esa corrupcion cae dentro de
la cadena JSON, el objeto deja de ser JSON valido, `_parse_router_response`
devuelve `None` y se lanza `RoutingError`.

**Y ahi esta el desperdicio.** El parser exige tres campos -`domain`,
`confidence` numerica en [0,1] y `reason` string- pero el core solo necesita
`domain` para enrutar. `reason` es texto libre en prosa: es el campo mas largo,
el que lleva los acentos y, por tanto, el que concentra la probabilidad de
corromperse. Se esta tirando una clasificacion correcta y con confianza alta
porque venia acompanada de una frase mal codificada.

Se explica tambien por que fallan unos dominios y no otros: `codigo` y `linux`
producen razones cortas y con menos acentos que `humanidades` y `matematicas`.
No es que esos dominios esten peor descritos; es que sus explicaciones son mas
largas.

## Por que la conformidad no lo veia

La bateria enruta contra un router guionizado que siempre devuelve un objeto
bien formado. Es correcto para fijar la semantica y no puede ver esto. Es el
mismo motivo por el que existen las fichas v0.3/0001 y v0.3/0002: parsers que
solo se rompen contra un modelo real.

## Cambio

Dos medidas independientes, y cada una ataca una cosa distinta.

### 1. `reason` deja de ser obligatorio

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

### 2. Un reintento antes de degradar

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
- En laboratorio, la tanda de 4 prompts x 3 intentos mejora de forma medible
  respecto al 1/3 registrado. Se anota el numero, no "parece mejor".

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

Pendiente.
