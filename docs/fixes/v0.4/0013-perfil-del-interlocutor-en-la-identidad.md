# 0013: el contexto de identidad dice que clase de interlocutor es

Estado: implementada (2026-10-29)
Tipo: campo aditivo en el contrato
Impacto de version: patch
Version objetivo: v0.4.2

Origen: `edge CR-0001` (core#44,
`ia_nest_meta/docs/change_requests/from-ia_nest_edge/solicitado/CR-0001-perfil-del-interlocutor-en-la-identidad.md`).
Bloquea la entrada de la familia (hito `H08` de la hoja de ruta de meta, paso
H08P9).

## Problema

El borde sabe si quien habla es un adulto o un nino, y debe poder decirselo al
ente como un HECHO sobre el interlocutor, no como una instruccion (ADR 0033). El
contexto de identidad tiene cinco campos cerrados y `Identity.from_defaults`
solo lee esos cinco: un campo mas se descarta en silencio. Para el perfil
infantil, ese silencio es el peor fallo posible.

## Cambio

Un sexto campo opcional en el contexto de identidad:

    interlocutor_profile: "adult" | "child"

- Ausente o vacio: sin dato (`""`), igual que los demas campos opcionales.
- Un valor fuera del vocabulario es error de validacion de la peticion, no un
  descarte silencioso: el consumidor recibe el mismo error tipado que con
  cualquier otro parametro invalido (400 en REST).
- El core lo TRANSPORTA y lo TRAZA, y no lo interpreta: no cambia modelo,
  perfil, dominio, enrutado ni prompt por el. Lo leen quienes lo necesiten
  (hoy extended, manana los checkpoints de conscience).
- Se refleja en la traza y en la telemetria como los otros cinco campos.
- Vale en todas las capacidades que transportan identidad (`prompt.*`,
  `reasoning.*`, `task.*`, `domain.route`) y en todos los transportes (REST,
  MCP, CLI).
- La identidad por defecto del operador local no lo fija: sin dato.

No cambia:

- el tratamiento de cualquier otro campo desconocido de la identidad;
- ninguna salida para quien no manda el campo, salvo que la traza gana la
  clave con valor vacio (aditivo).

## Criterios de aceptacion

- Con `interlocutor_profile: "child"` en `prompt.run`, `prompt.stream`,
  `reasoning.run`, `reasoning.stream`, `task.run`, `task.stream` y
  `domain.route`, el valor aparece en la traza de la respuesta y en los eventos
  de telemetria de esa peticion, tambien en los de las subtareas de `task.*`.
- Con `"adult"`, igual.
- Sin el campo, la traza lo lleva vacio y nada mas cambia.
- Con un valor fuera del vocabulario (`"teen"`, `"CHILD"`, un numero), la
  peticion se rechaza con el error de validacion; no llega al modelo.
- La misma peticion con `"child"` y con `"adult"` resuelve el mismo modelo,
  perfil y dominio, y manda al modelo los mismos mensajes.
- Ningun test ni caso de conformidad existente cambia de salida salvo por la
  clave nueva en la traza.

## Archivos previstos

- `src/ianest_core/identity.py` y los puntos que componen la identidad o la
  vuelcan en la traza
- `docs/CORE_CONTRACT.md` (campos del contexto de identidad)
- `CHANGELOG.md` (seccion sin publicar)
- tests y, si la bateria de conformidad cubre la identidad, sus casos

## Telemetria

`interlocutor_profile` lleva el esquema de telemetria a `schema_version` `2`
en CSV y JSONL. En CSV es la columna 19, al final, despues de `error_type`;
las primeras 18 columnas conservan exactamente el orden de ADR 0015 para no
romper lectores por posicion. Antes de anadir a un CSV existente no vacio, el
escritor comprueba una vez por fichero y proceso que su cabecera coincide con
el esquema actual. Si no coincide, rota el fichero y crea otro con la cabecera
correcta, para no mezclar filas de distinto esquema.

ADR 0015 exige subir `schema_version` y registrar la decision cuando cambian
columnas o campos. Esta ficha registra la decision y su motivo.

## Resultado

- Implementado en la rama `feat/v0.4.2-perfil-interlocutor`.
- Validado con 323 tests y 136/136 casos de conformidad; digest
  `f6558d3c7e16d20c453c3696e121e105e5869ebfb06f0d4fd9fff6849ceaff57`.
