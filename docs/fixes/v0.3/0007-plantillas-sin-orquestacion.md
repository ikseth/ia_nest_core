# 0007: las plantillas de configuracion no permiten ejecutar task.run

Estado: implementada
Tipo: correccion
Impacto de version: patch
Version objetivo: v0.3.0

## Problema

Ni `config/core.example.yaml` ni `config/core.lab.example.yaml` declaran la
seccion `orchestration`. `TaskRuntime.__init__` la exige, asi que despues de
`ianest init` -con cualquiera de las dos plantillas- el comando falla:

    ConfigError: task.run requires the optional orchestration configuration
    section

`task.run` es la capacidad central de las lineas v0.2 y v0.3 y no es alcanzable
desde el camino de instalacion documentado. Quien sigue
`docs/manual/instalacion.md` de principio a fin obtiene un core que no puede
orquestar.

Verificado tambien en el host de laboratorio: su `config/core.yaml` SI tiene la
seccion, anadida a mano en cuatro iteraciones sucesivas entre el 17 y el 23 de
julio (consta en los backups del propio host). Es decir: la seccion se ha
tenido que reconstruir a mano en cada instalacion real.

## Cambio

Las DOS plantillas declaran `orchestration` (decision del usuario,
2026-08-06).

- `core.lab.example.yaml`: roster multi-modelo ya existente, con `planner`,
  `combiner` y `coverage.validator` declarados y los limites por defecto.
- `core.example.yaml`: plantilla minima de un solo modelo. Los tres roles
  apuntan a `local_llama`, el unico modelo declarado. Es orquestacion
  mono-modelo: no aprovecha el reparto por dominios, pero es honesta y
  funcional, y hace que `task.run` responda desde el primer contacto.

Se anade un comentario en la plantilla minima explicando que con un solo modelo
la orquestacion no reparte por dominio, y que la plantilla `lab` es la que
muestra el reparto real.

Los valores por defecto de los limites se toman de los que ya fija
`OrchestrationConfig` en el esquema, para que plantilla y esquema no diverjan.

## Nota sobre max_subtasks

El techo por defecto del esquema es 4. La evidencia de laboratorio
(ADR 0041, ocho planetas: 16 unidades derivadas contra un techo de 12) muestra
que un techo bajo convierte planes correctos en tareas muertas. Esta ficha NO
cambia el valor por defecto: bajo ADR 0041 un techo deja de ser muerte subita
(I2 negocia, I3 no lo disfraza de exito), con lo que el valor deja de ser
critico. Si tras implementar ADR 0041 la evidencia pide subirlo, sera su propia
ficha.

## Criterios de aceptacion

- `ianest init --template minimal` seguido de `ianest task run --prompt "..."`
  no falla con `ConfigError`; ejecuta la orquestacion contra el unico modelo
  declarado.
- Lo mismo con `--template lab`.
- `ianest config validate` acepta las dos plantillas.
- Test que ejecuta `config.validate` sobre AMBAS plantillas y comprueba que
  declaran `orchestration`, para que el hueco no se reabra.
- Los limites de las plantillas coinciden con los valores por defecto del
  esquema (`OrchestrationConfig`).
- Conformance sin cambio de digest: las plantillas no participan en la bateria,
  que usa sus propias fixtures.
- pytest en verde con y sin extras.

## Archivos previstos

- `config/core.example.yaml`
- `config/core.lab.example.yaml`
- `tests/test_init.py`
- `docs/manual/configuracion.md`

## No cubre

- Que `ianest init` VERIFIQUE que `task.run` es alcanzable con la config que
  acaba de crear (hoy solo valida el YAML). Es una capacidad nueva del comando
  `init`, no una correccion de plantilla; si se quiere, ficha propia.
- El conflicto entre `max_tokens` por llamada y `max_context_tokens` acumulado
  de la tarea, que en el laboratorio estan ambos en 4096 y hacen que una sola
  llamada pueda agotar el presupuesto entero. Es una cuestion de semantica de
  limites y necesita ADR (pendiente, punto B5 del plan de correcciones).

## Resultado

Implementada en las dos plantillas y sus pruebas de inicializacion.
