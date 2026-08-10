# 0011: el contrato de dependencias de pipeline, dicho y tolerado

Estado: propuesta
Tipo: correccion (robustez del planificador, modo pipeline)
Impacto de version: patch
Version objetivo: v0.3.x

## Problema

`task.run` en modo `pipeline` pierde tareas enteras porque el planificador
devuelve `depends_on` en una forma que el codigo rechaza. Muere en la primera
llamada, con `exit != 0` y sin producir nada.

### La causa raiz es nuestra instruccion, no el modelo

Las dos etapas de planificacion piden `depends_on` de forma MUY distinta:

- `_plan_coverage`: "...optional `depends_on` **as a list of ids**", y su parseo
  tiene `_coerce_unit_id`, que acepta entero y cadena.
- `_plan` (pipeline): "...optional `depends_on`", y nada mas. No dice que
  contiene, ni de que tipo, ni en que base.

Y despues `_dependencies` exige `int` estricto y lanza `PlanDependencyError` si
no lo es. Le pedimos al planificador un campo sin decirle su forma y lo matamos
por no adivinarla.

### La evidencia

Telemetria del laboratorio, 2026-08-10, sobre los planes de PIPELINE parseables
acumulados (24 planes; los de coverage se excluyen porque su contrato es otro):

- 11 de 24 declaran dependencias;
- dentro de `depends_on`: **35 valores enteros y 4 cadenas** (`"1"`, `"2"`,
  `"3"`).

Es decir: el modelo acierta el SIGNIFICADO -el indice correcto- y falla el TIPO,
porque lo entrecomilla. En la puerta de laboratorio de la ficha 0010, 1 de 9
ejecuciones reales de `task.run` murio por esta causa.

La muestra es corta para acreditar una mejora, y por eso esta ficha lleva puerta
de medicion propia (mas abajo); es suficiente para acreditar el DIAGNOSTICO,
porque la forma del fallo es inequivoca.

### Un segundo problema, latente y NO medido

La instruccion tampoco dice si el indice es base 0 o base 1. Los valores
observados (aparece el `0`, y un patron de pares 2-4-6-8 coherente con planes de
16 unidades) sugieren que el modelo usa base 0, pero eso es inferencia, no
medicion.

Importa porque falla en SILENCIO: un indice base 1 dentro de rango no da error,
solo ordena mal las dependencias y nadie se entera. Uno fuera de rango si
revienta, pero con el mensaje equivocado -"plan contains cyclic or invalid
dependencies", emitido desde `_fan_out` cuando ningun subtarea queda lista-,
que manda a diagnosticar un ciclo donde hay un indice invalido.

### Asimetria de fondo

`coverage` ya recibio dos veces este mismo tratamiento (fichas v0.3/0001 y
v0.3/0002, ambas "tolerante"): instruccion explicita y parseo que acepta las
formas razonables. `pipeline` se quedo estricto. Esta ficha le da el mismo
trato, sin inventar diseno nuevo: reutiliza el patron que coverage ya tiene.

## Cambio

### A. Decir la forma en la instruccion

`_plan` declara explicitamente que `depends_on` es una lista de indices ENTEROS
en BASE 0 sobre esa misma lista. Cierra la ambiguedad en origen y cubre de paso
el problema de la base, que no tiene otra defensa posible: un indice base 1
dentro de rango es indetectable desde el codigo.

### B. Tolerancia simetrica en `_dependencies`

Una cadena que sea un digito se acepta y se convierte, igual que
`_coerce_unit_id` de coverage acepta el entero. Aplica tanto a la lista como al
valor suelto, que ya se aceptaba en su forma entera.

Una cadena NO numerica sigue siendo `PlanDependencyError`: en `pipeline` no hay
ids a los que referirse, asi que no hay nada que interpretar. La tolerancia
llega hasta donde hay significado recuperable, y ni un paso mas.

Se anade ademas la guarda de booleanos que coverage ya tiene: en Python
`isinstance(True, int)` es cierto, y hoy un `depends_on: [true]` pasaria por
indice 1.

### C. Validar las dependencias al planificar, no a mitad del fan-out

`pipeline` gana el equivalente de `_validate_coverage_dependencies`: tras
parsear el plan se comprueba que todo indice este dentro de rango y que el grafo
no tenga ciclos, con `PlanDependencyError` y mensajes que distingan un caso del
otro.

Dos ganancias: el error dice lo que pasa de verdad -indice invalido deja de
disfrazarse de ciclo- y la tarea no gasta llamadas antes de descubrir que su
plan no era ejecutable. El tipo de error no cambia (`PlanDependencyError`, campo
`depends_on`); cambia el mensaje, que no es contrato (ADR 0020).

## Criterios de aceptacion

- Un plan con `depends_on: ["1"]` se ejecuta igual que con `[1]` (test).
- Un plan con `depends_on: "1"` (valor suelto) se comporta como `[1]` (test).
- Un plan con `depends_on: ["a"]` sigue dando `PlanDependencyError` con campo
  `depends_on` (test).
- Un plan con `depends_on: [true]` da `PlanDependencyError` y NO se interpreta
  como indice 1 (test).
- Un plan con un indice fuera de rango da `PlanDependencyError` con mensaje de
  indice invalido, ANTES de ejecutar ninguna subtarea (test que cuenta las
  llamadas al adaptador).
- Un plan con ciclo da `PlanDependencyError` con mensaje de ciclo (test).
- La instruccion de `_plan` menciona indices enteros base 0 (test de unidad
  sobre el texto, patron de la ficha v0.3/0003).
- Un plan valido sin dependencias y uno con dependencias enteras se comportan
  EXACTAMENTE igual que hoy (no regresion).
- **Digest de conformance SIN cambio**: la bateria no tiene ningun caso de
  dependencias de pipeline -verificado sobre `conformance.yaml`,
  `v0.2/orchestration.yaml` y `router/domain_route.yaml`-, asi que este cambio
  no puede moverlo. Si se mueve, el cambio se fue de alcance.
- pytest en verde con y sin extras; sin dependencias nuevas.
- No toca `coverage` ni `_coerce_unit_id`.

## Puerta de laboratorio (medicion, no impresion)

El diagnostico se midio; la mejora tambien debe medirse, y sin pagar tareas
completas a ~52 s.

Se aisla el planificador lanzando su instruccion tal cual con `prompt run`
contra el modelo planificador, N=20 antes y N=20 despues, y se cuenta la
distribucion de formas de `depends_on` (entero, cadena numerica, cadena no
numerica, ausente). Criterio: la proporcion de valores en cadena baja de forma
visible; ninguna forma nueva aparece.

La segunda mitad de la puerta la cubre el codigo: aunque el planificador siga
entrecomillando de vez en cuando, la tolerancia de B hace que ya no cueste la
tarea. Son dos defensas independientes y se verifican por separado.

## Archivos previstos

- `src/ianest_core/runtime/task_runtime.py` (`_plan`, `_dependencies`,
  validacion nueva de dependencias de pipeline)
- `tests/test_task_runtime.py`
- `docs/fixes/v0.3/0011-dependencias-de-pipeline-tolerantes.md`
- `CHANGELOG.md`

## No cubre

- **Que un plan malformado deje de matar la tarea.** Es lo que la doctrina de
  ADR 0041 pide ("un limite negocia antes de matar"): gastar la re-derivacion
  unica de I1/I2 tambien cuando el plan no es ejecutable. Pero ADR 0041 fijo ese
  contador como uno por tarea compartido entre I1 e I2, y anadir una TERCERA
  causa es una decision, no una inferencia. Ademas I1/I2 siguen sin implementar
  (fase B, con su bateria congelada). Entra como extension de ADR 0041 cuando se
  implemente esa fase, no como ADR suelto.
- El indice base 1 DENTRO de rango: indetectable desde el codigo. La unica
  defensa es la instruccion del cambio A.
- `PlanParseError` por JSON invalido, que es otra familia de fallo del
  planificador.
- El contrato de `depends_on` de `task.plan` (ADR 0040, sin implementar): esta
  ficha no lo fija, solo alinea la forma que el planificador propio produce.

## Resultado

(pendiente de implementacion)
