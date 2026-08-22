# 0009: el ejemplo publicado sirve de fabrica el fallo que su propio comentario describe

Estado: implementada (2026-08-22), con una puerta de laboratorio pendiente
Tipo: correccion de artefacto publicado
Impacto de version: patch
Version objetivo: v0.4.x

Origen: hallazgo 3 del brief de `ia_nest_extended` del 2026-08-22
(`ia_nest_meta/docs/handoff/avisos_al_core_desde_extended_2026-08-22.md`,
issue #36). Disposicion: ADR 0051, decision D6.

## Problema

`config/core.lab.example.yaml` diagnostica correctamente, en un comentario del
bloque `orchestration`, que un modelo de razonamiento no sirve como planificador:
emite su cadena de pensamiento antes de la respuesta y con `max_tokens: 512` el
pensamiento agota el presupuesto. El planificador se arreglo con ese
diagnostico.

Y a continuacion el mismo fichero dejaba el dominio `razonamiento` servido por
ESE modelo con el perfil `default`, de 512 tokens, justificandolo con que ese
dominio "es su sitio". El sitio es correcto; el presupuesto no.

Medido por extended: las subtareas de ese dominio salen con
`finish_reason: length` y **cadena vacia** -ADR 0042 sanea el canal de
razonamiento en origen, y si `<think>` nunca se cierra no queda nada fuera de
el-, o con texto corrompido.

El despliegue real del laboratorio ya no lo sufre, porque su roster define un
perfil aparte. Esta ficha es sobre el ARTEFACTO PUBLICADO: quien arranque por el
ejemplo se encuentra el fallo servido de fabrica.

## Cambio

En `config/core.lab.example.yaml`:

1. Perfil `razonamiento` propio, con `max_tokens: 2048` y `max_time_s: 120`, y el
   dominio `razonamiento` pasa a usarlo. El comentario explica POR QUE existe el
   perfil y declara que la cifra es un punto de partida, no una medida.
2. Perfil `planificador` con `temperature: 0.0`, que el planificador usa. Cubre
   la parte legitima del hallazgo 2 sin tocar el core (ADR 0051, D5): el
   determinismo del plan es palanca del operador, y los parametros del perfil
   viajan al backend tal cual. El comentario apunta ademas a la via del core para
   medidas reproducibles -congelar el plan con `task.plan`- y a `seed` como
   opcion dependiente del backend.
3. El comentario de `orchestration` deja de decir media verdad: `deepseek_reason`
   sigue siendo el modelo del dominio `razonamiento`, pero NO con el perfil de
   512.

No toca codigo, ni esquema, ni contrato. Es una plantilla.

## Criterios de aceptacion

Verificados el 2026-08-22:

- `config.validate` acepta el ejemplo con el endpoint resuelto (`ok`).
- Ningun dominio servido por un modelo de razonamiento comparte el perfil de 512
  tokens.
- El comentario del fichero no afirma nada que el propio fichero contradiga.
- Digest de conformidad INTACTO: el ejemplo no participa en la bateria.

Puerta pendiente, en laboratorio (declarada tambien en ADR 0051):

- Con el ejemplo corregido y `deepseek-r1:8b`, una subtarea del dominio
  `razonamiento` devuelve cadena NO vacia. Si 2048 no basta, la cifra se corrige
  aqui con la medida delante, no por estimacion.

## Archivos

- `config/core.lab.example.yaml`

## No cubre

- Que el core integre el vacio sin declararlo, que es el defecto de fondo que
  este ejemplo destapo y que dispone ADR 0051 (D3). Esta ficha arregla la
  plantilla; el core seguiria callandose el vacio con cualquier otra.
- `config/core.example.yaml`, la plantilla minima, que no declara roster de
  razonamiento.
