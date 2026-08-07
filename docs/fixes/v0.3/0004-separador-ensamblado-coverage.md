# 0004: separador determinista en el ensamblado del modo coverage

Estado: implementada
Tipo: correccion
Impacto de version: patch
Version objetivo: v0.3.0

## Problema

`_assemble_coverage` une los fragmentos aceptados con `"".join(...)`. Sin
separador, el final de un fragmento y el principio del siguiente se pegan y
corrompen palabras.

Evidencia de laboratorio (2026-08-05, prompt de los ocho planetas, 8 unidades,
`coverage_complete=true`):

    MercurioEl segundo planeta del sistema solar es Venus.El tercer planeta...

`Mercurio` + `El segundo...` produce `MercurioEl`. La respuesta correcta unidad
a unidad sale ilegible al ensamblarse.

ADR 0038 fija "concatenacion determinista en el orden requerido" y no llego a
fijar con que se concatena. No es una decision de estilo pendiente: sin
separador el ensamblado no preserva el contenido que valido el validador.

## Cambio

`_assemble_coverage` une los fragmentos con un separador fijo de linea en
blanco (`\n\n`), aplicando `strip()` a cada fragmento para no acumular saltos
cuando el modelo ya cierra con salto.

Separador FIJO, no configurable: no hay caso que pida regularlo
(anti-entropia). Si aparece, se promueve entonces.

## Consecuencia sobre la bateria

`eval/battery/v0.3/coverage.yaml` asierta las respuestas ensambladas de forma
literal (`response: ABCD`, `FIRSTLAST`, `FIRSTSECONDTHIRD`,
`CODEREASONGENERAL`, `ONETWOTHREE`, `ONE`). Los ocho casos que asertan
`response` cambian de valor esperado.

Esto NO relaja la bateria: las expectativas siguen fijando el mismo orden
determinista, solo que con el separador visible (`A\n\nB\n\nC\n\nD`). El digest
de conformance cambia y se DECLARA, con el patron de v0.2-3 y v0.3-2
(ADR 0017).

## Criterios de aceptacion

- Dos fragmentos consecutivos nunca quedan pegados; existe test de unidad sobre
  el ensamblado con fragmentos que no terminan en signo de puntuacion.
- El orden determinista de ADR 0038 no cambia: mismo orden, mismo contenido.
- Un fragmento que ya termina en salto de linea no genera separacion doble.
- `eval/battery/v0.3/coverage.yaml` actualizado en los ocho casos que asertan
  `response`; conformance en verde con digest recalculado y declarado.
- El digest de la linea v0.2 (pipeline) no cambia: el ensamblado de coverage no
  toca pipeline.
- pytest en verde con y sin extras; sin dependencias nuevas.

## Archivos previstos

- `src/ianest_core/runtime/task_runtime.py`
- `eval/battery/v0.3/coverage.yaml`
- `eval/README.md` (digest declarado; el anterior queda como historico)
- `tests/test_task_coverage.py`

## No cubre

La heterogeneidad de formato entre fragmentos (unos titulan, otros responden en
frase completa) es la ficha 0005 de esta misma linea. La pasada de "voz del
ente" que homogeneizaria el resultado final sigue diferida
(`CAPAS_FUTURAS.md`), y esta ficha no la adelanta: separar fragmentos para que
no se corrompan es preservar el contenido, no darle forma.

## Resultado

Implementada con separador fijo `\n\n`, fragmentos normalizados con `strip()`,
bateria coverage actualizada y digest declarado.
