# 0010: un flujo que termina a medias es indistinguible de uno que termina bien

Estado: propuesta
Tipo: hueco de declaracion en el adaptador
Impacto de version: patch (previsto)
Version objetivo: v0.4.x

Origen: aparecio midiendo la [ficha v0.4/0009](0009-el-ejemplo-publicado-sirve-su-propio-fallo.md)
en laboratorio el 2026-09-11. No estaba en ningun brief: lo destapo repetir.

## Problema

El adaptador compatible con OpenAI construye su evento `done` al SALIR del
bucle de lectura del flujo, con el `finish_reason` que haya visto. Si el flujo
del backend termina sin enviar `finish_reason` -y sin `[DONE]`-, el adaptador
emite igualmente un `done`, con `finish_reason: null` y `tokens_out: 0`.

Aguas abajo nadie distingue eso de una terminacion limpia. `prompt.run` devuelve
`status: ok`, y el texto que hubiera llegado hasta el corte se entrega como si
fuera la respuesta completa.

## Lo medido

Contra el backend del laboratorio, con el mismo prompt y parametros, 5 pasadas:

    finish=None  tokens_out=None  len=1769   cadena sin cerrar
    finish=None  tokens_out=None  len=1127   cadena sin cerrar
    finish=None  tokens_out=None  len=1703   cadena cerrada
    finish=length tokens_out=4096 len=6713   cadena sin cerrar
    finish=None  tokens_out=None  len=1969   cadena sin cerrar

**Cuatro de cinco** terminan sin motivo de corte. A traves del core, el mismo
modo aparecio 3 veces en unas 20 llamadas, con `latency_ms` en torno a 9000,
`tokens_in: 0`, `tokens_out: 0` y `status: ok` en la traza.

No se sabe todavia por que el backend corta el flujo; averiguarlo es parte de
esta ficha y no se supone aqui. Lo que si esta medido es la consecuencia en el
core: **el core no puede decir si su respuesta esta entera.**

## Por que importa, y donde encaja

Es el mismo patron que ADR 0051 dispuso para la subtarea vacia, un nivel mas
abajo y en el camino comun a TODAS las capacidades, no solo a `task.run`. La
diferencia es que aqui ni siquiera hay una senal que mirar: `finish_reason` es
nulo, y nulo se lee hoy como "nada que declarar".

`task.run` hereda el problema: una subtarea cortada a medias entra al combinador
como un resultado sano, y esta vez con texto, asi que R1 de ADR 0051 -que se
dispara con la respuesta VACIA- no la atrapa.

## Cambio propuesto

Que el core distinga las dos terminaciones y lo declare. Forma por decidir en su
fase de contrato; las dos candidatas obvias:

- un `finish_reason` sintetico y explicito (por ejemplo `incomplete`) cuando el
  flujo termina sin que el backend declare ninguno, en vez de nulo;
- o un error tipado del adaptador, si se decide que un flujo cortado no es una
  respuesta.

La primera conserva el texto ya recibido, que es util; la segunda es mas
estricta. La eleccion cambia el contrato de una forma u otra, asi que se decide
antes de implementar y no al reves.

## Criterios de aceptacion (previstos)

- Caso de conformidad: flujo que termina sin `finish_reason` y sin `[DONE]` ->
  el core lo declara, por la via que se elija, y NO lo reporta como terminacion
  limpia.
- Caso de conformidad: flujo normal -> salida identica a la actual, byte a byte.
- La bateria puede guionizar un flujo truncado. Hoy no puede: es la misma
  carencia de utillaje que ADR 0051 anoto para `finish_reason`.
- En laboratorio, el modo se reproduce y queda declarado en la traza.

## Archivos previstos

- `src/ianest_core/adapters/openai_compatible.py`, `src/ianest_core/adapters/base.py`
- `docs/CORE_CONTRACT.md`, bateria y `eval/README.md`

## No cubre

- La causa en el backend, que es de la instalacion y no del core, aunque haya
  que investigarla para poder reproducir el caso.
