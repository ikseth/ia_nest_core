# 0009: el ejemplo publicado sirve de fabrica el fallo que su propio comentario describe

Estado: implementada (2026-09-11), verificada en laboratorio
Tipo: correccion de artefacto publicado
Impacto de version: patch
Version objetivo: v0.4.x

Origen: hallazgo 3 del brief de `ia_nest_extended` del 2026-08-22
(`ia_nest_meta/docs/handoff/avisos_al_core_desde_extended_2026-08-22.md`,
issue #36). Disposicion: ADR 0051, decision D6.

**Esta ficha se reescribio el 2026-09-11.** Su primera version (2026-08-22)
diagnostico la causa como falta de presupuesto y la arreglo subiendo
`max_tokens` a 2048. Al medirlo en laboratorio, ese arreglo NO arreglaba nada:
el dominio seguia devolviendo cadena vacia. Lo que sigue es el diagnostico
medido, no el deducido.

## Problema

`config/core.lab.example.yaml` servia el dominio `razonamiento` con un modelo de
razonamiento -deepseek-r1:8b- y el perfil `default`, de 512 tokens. Medido por
extended: subtareas con `finish_reason: length` y cadena vacia, porque el core
sanea el canal de razonamiento en origen (ADR 0042) y una cadena `<think>` que
nunca cierra no deja nada fuera de ella.

El comentario del propio fichero diagnosticaba bien el mecanismo para el
PLANIFICADOR y a la vez dejaba el dominio servido por ese modelo, con la
justificacion de que ese dominio "es su sitio".

## La causa no era el presupuesto

Medido en laboratorio el 2026-09-11, por el cable, contra deepseek-r1:8b:

    max_tokens 2048, temp 0.2   finish_reason length, cadena vacia   (4 pasadas)
    max_tokens 4096, temp 0.2   finish_reason length, cadena vacia   (2 pasadas)
    max_tokens 8192, temp 0.2   finish_reason length, cadena vacia   (1 pasada)
    "cuanto es 2+2", 4096       finish_reason length, cadena vacia   (2 pasadas)

La ultima linea es la que cierra el argumento: una pregunta trivial tambien
agota 4096 tokens. Mirado el crudo del backend, el modelo entra en BUCLE DE
REPETICION dentro de la cadena de pensamiento -`" El. El. El. El."` hasta
agotar el techo- y `</think>` no llega nunca.

Con el muestreo que el propio modelo recomienda (`temperature: 0.6`,
`top_p: 0.95`) el bucle desaparece, pero la cadena sigue sin ser fiable: con una
pregunta trivial cerro 3 de 3 veces, y con un silogismo sencillo cerro **1 de 5**
con techo de 4096. La longitud del pensamiento varia demasiado entre pasadas del
mismo prompt como para que exista un techo que lo garantice.

Correccion a la sugerencia del brief, que tambien se midio: el brief propuso
"que el ejemplo lleve el perfil de razonamiento que el propio laboratorio ya
usa". Ese perfil, por si solo, no habria arreglado el ejemplo. El roster real
del laboratorio resolvio el problema con DOS cambios, y el brief conto uno: el
perfil de 2048 tokens **y** sacar el dominio `razonamiento` del modelo de
razonamiento, que alli lo sirve un modelo normal.

## Cambio

En `config/core.lab.example.yaml`:

1. El dominio `razonamiento` pasa a `qwen_tech` con un perfil propio de 2048
   tokens. Motivo del perfil, sin misterio: una respuesta paso a paso no cabe en
   512 tokens.
2. El modelo de razonamiento sale del ejemplo, tambien como fallback de los
   dominios tecnicos, donde arrastraba el mismo fallo un nivel mas abajo.
3. El comentario cuenta lo medido -las dos tablas de arriba- y dice que si
   despliegas un modelo de razonamiento tienes que medirlo en tu instalacion
   antes de ponerlo a servir un dominio.

No toca codigo, ni esquema, ni contrato. Es una plantilla.

Lo que NO se hizo, y por que: no se busco "el techo bueno". No lo hay. Poner una
cifra mayor habria sido repetir el error de la primera version de esta ficha con
un numero mas grande.

## Criterios de aceptacion

Verificados el 2026-09-11:

- `config.validate` acepta el ejemplo con el endpoint resuelto (`ok`).
- **Puerta de laboratorio, 3 de 3**: con el ejemplo corregido,
  `prompt.run --domain razonamiento` devuelve `finish_reason: stop` y respuesta
  real en espanol (430, 478 y 637 caracteres), servida por `qwen_tech`.
- Ningun dominio del ejemplo, ni por preferencia ni por fallback, queda servido
  por un modelo cuya cadena de pensamiento el ejemplo no ha medido.
- El comentario del fichero no afirma nada que el propio fichero contradiga.
- Digest de conformidad INTACTO: el ejemplo no participa en la bateria.

## Archivos

- `config/core.lab.example.yaml`

## No cubre

- Que el core integre el vacio sin declararlo, que es el defecto de fondo que
  este ejemplo destapo y que dispone ADR 0051 (D3). Esta ficha arregla la
  plantilla; el core seguiria callandose el vacio con cualquier otra, y ahora se
  sabe ademas que NINGUNA configuracion lo evita del todo.
- El flujo que termina sin `finish_reason`, aparecido midiendo esto:
  [ficha v0.4/0010](0010-fin-de-flujo-sin-motivo-de-corte.md).
- `config/core.example.yaml`, la plantilla minima, que no declara roster de
  razonamiento.
