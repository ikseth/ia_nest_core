# 0012: subtareas que ven la tarea, y un combinado que no se contradice

Estado: implementada
Tipo: correccion (dos defectos encadenados del modo pipeline)
Impacto de version: patch
Version objetivo: v0.3.x

## Problema

Una tarea de `task.run` en modo `pipeline` puede devolver una respuesta que se
contradice a si misma. Medido en laboratorio el 2026-08-11, con la pregunta
sobre la leyenda del numero que aparece en el cine.

### A. Las subtareas se ejecutan A CIEGAS

`_run_subtask` envia al modelo UNICAMENTE `item["prompt"]`: el enunciado que el
planificador escribio para esa subtarea, sin la tarea de la que forma parte.

Consecuencia medida, en una sola ejecucion real de ocho subtareas:

- "Buscar informacion sobre la leyenda del numero en internet" -> el modelo no
  sabe de que numero se habla, y responde sobre el **666** y el Apocalipsis;
- "Identificar el numero en cuestion (si es el 47 o algun otro)" -> "Lo siento,
  pero no entiendo la pregunta";
- "Encontrar peliculas donde se haya reportado la aparicion del..." -> responde
  sobre el **7**.

Tres subtareas, tres numeros distintos, ninguno el de la pregunta. No es un
fallo de los modelos: es que nadie les dijo de que iba la tarea.

El modo `coverage` NO tiene este defecto, y lo resolvio hace tiempo: su prompt
de generacion lleva `"Global objective (CONTEXT ONLY; do not answer it as a
whole)"` (ADR 0038). `pipeline` nunca lo llevo. Es la misma asimetria que ya
corrigieron las fichas v0.3/0001, 0002 y 0011: un modo aprendio y el otro no.

### B. El combinador no tiene encargo de coherencia

La instruccion completa de COMBINE es hoy: *"Combine the subtask results into
one answer"*. Con eso, lo unico que puede hacer es GRAPAR los fragmentos. Si uno
afirma que el numero es 47 y otro que es 119, la respuesta final afirma las dos
cosas, en parrafos distintos, como si nada.

Arreglar A reduce mucho la divergencia, pero no la elimina: dos subtareas con
contexto pueden seguir discrepando. Y una respuesta que se contradice a si misma
es un defecto sea cual sea su causa.

## Cambio

### A. El objetivo global viaja como CONTEXTO a cada subtarea

`_run_subtask` compone el prompt de la subtarea con la tarea global marcada como
contexto, reutilizando LITERALMENTE el guardarrail que `coverage` ya tiene: el
objetivo se presenta como contexto que NO hay que responder entero, y la
subtarea sigue siendo lo unico que se produce.

No se inventa formato: se copia el patron de `_coverage_generation_prompt`, que
lleva en produccion desde la ficha v0.3/0003 y esta verificado en laboratorio.

### B. COMBINE recibe encargo de coherencia

La instruccion de COMBINE pasa a exigir que la respuesta sea internamente
consistente. Cuando dos fragmentos afirmen cosas incompatibles sobre el mismo
punto, el combinador NO puede presentarlas ambas como hechos: las presenta como
lo que son, versiones divergentes, y sigue.

La frontera, que es lo que hace que esto sea core y no otra capa:

- **Estructurar SI**: detectar que dos fragmentos discrepan y ordenar la
  respuesta para que no se contradiga.
- **Juzgar NO**: decidir cual de los dos es cierto. Eso es exactitud factual, y
  sigue fuera del core (ADR 0025, territorio de `ia_nest_core_conscience`).

No es una capacidad nueva ni un modelo de control juzgando a otro: el combinador
YA lee y funde las salidas de los otros modelos, que es su descripcion de puesto
en ADR 0036. Lo que faltaba era decirle que el resultado tiene que sostenerse en
pie.

Riesgo a vigilar, y por eso la puerta de laboratorio lo mide: que el combinador
se vuelva cauteloso de mas y empiece a matizar donde no hay divergencia. La
instruccion lo prohibe de forma explicita, y la medida lo comprueba.

### Lo que NO cambia

`coverage` no recibe la parte B. Su respuesta final es el ENSAMBLADO
DETERMINISTA de los fragmentos aceptados, sin reescritura global, y eso es una
decision tomada en ADR 0038 con motivo: reescribir romperia la correspondencia
entre lo que el validador acredito y lo que sale. La asimetria es deliberada, no
un olvido.

La parte A si aplicaria a coverage, pero alli ya esta hecha desde ADR 0038.

## Criterios de aceptacion

- El prompt que recibe una subtarea contiene el objetivo global marcado como
  contexto y la instruccion de no responderlo entero (test de unidad sobre el
  texto compuesto, patron de la ficha v0.3/0003).
- La subtarea sigue recibiendo su propio enunciado como el unico contenido a
  producir.
- La instruccion de COMBINE contiene el encargo de coherencia y la prohibicion
  de matizar cuando no hay divergencia (test de unidad sobre el texto).
- `coverage` sin cambios: ni su generacion ni su ensamblado se tocan.
- **Digest de conformance**: se declara ANTES de implementar cual es la
  expectativa. Los casos de conformance usan adaptadores fake guionizados, cuyas
  respuestas no dependen del texto del prompt, asi que el digest NO deberia
  moverse. **Si se mueve, PARA**: significaria que algun caso aserta el prompt
  compuesto y hay que declararlo.
- pytest en verde con y sin extras; sin dependencias nuevas.

## Puerta de laboratorio (medida, y por partes)

Las dos partes se miden POR SEPARADO, para saber que compra cada una. Con la
pregunta de la leyenda del numero, que es el caso que produjo la evidencia:

1. **Solo A**: se comprueba si las subtareas dejan de responder sobre numeros
   distintos. Metrica: numeros distintos mencionados entre los fragmentos de una
   misma ejecucion, sobre N ejecuciones.
2. **A + B**: se comprueba si el combinado sigue conteniendo afirmaciones
   incompatibles.
3. **Control de sobre-matizado**: una tarea cuyas subtareas NO discrepan (por
   ejemplo las tres definiciones de Linux, ya usada en la puerta de la ficha
   0010) no debe ganar matizaciones ni "segun algunas fuentes" que hoy no tiene.
   Es el riesgo de la parte B y se mide, no se supone.

## Archivos previstos

- `src/ianest_core/runtime/task_runtime.py` (`_run_subtask`, `_combine`)
- `tests/test_task_runtime.py`
- `docs/fixes/v0.3/0012-subtareas-con-contexto-y-combinado-coherente.md`
- `CHANGELOG.md`

## No cubre

- Decidir cual de dos afirmaciones divergentes es la correcta: exactitud
  factual, fuera del core (ADR 0025).
- Responder preguntas que necesitan busqueda web o RAG. La pregunta que produjo
  esta evidencia es justo de esas: el core puede dejar de contradecirse, pero no
  puede acertar el dato. Eso es `ia_nest_extended`.
- El ensamblado de `coverage` (ADR 0038, decision explicita).
- Pasar a la subtarea los resultados de las subtareas ANTERIORES, que es otra
  cosa distinta -y mas cara- que pasarle el objetivo. Si aparece el caso, ficha
  propia.

## Resultado

Implementado en `task_runtime.py`: cada subtarea de `pipeline` recibe el
objetivo global solo como contexto y su enunciado como unico contenido a
producir. El enrutado conserva el enunciado pelado de la subtarea y el registro
tambien lo conserva. COMBINE recibe instrucciones para estructurar versiones
divergentes sin decidir exactitud factual ni matizar cuando no hay divergencia.

Se anadieron pruebas del prompt compuesto, el enrutado pelado, el registro de
subtarea, la instruccion de COMBINE y los dos prompts sin cambios de coverage.
La bateria de conformance conserva 61/61 y el digest declarado; pytest pasa con
y sin extras de interfaces.
