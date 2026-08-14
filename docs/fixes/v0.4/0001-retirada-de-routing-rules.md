# 0001: retirada de routing_rules del esquema de configuracion

Estado: implementada
Tipo: retirada de una clave de configuracion ya sin uso (ejecuta ADR 0043)
Impacto de version: minor (rompe contrato de config, serie pre-1.0)
Version objetivo: v0.4.0 (tramo C de la linea)

## Problema

ADR 0043 decidio que `routing_rules.keywords` se retira: el enrutado pasa a ser
semantico y la `description` de cada dominio es la entrada normativa del
clasificador. El runtime cumplio: desde la fase 3b-ii (`65a2db0`), el
`DomainRouter` exige `router` en la config y no lee ni una palabra clave.

La clave, en cambio, sigue viva en la CONFIGURACION:

- `config/schema.py` la modela (`DomainConfig.routing_rules`),
- `config/loader.py` la carga,
- `config/validator.py` la valida (que sea mapa, y que `keywords`/`tags` sean
  listas).

No es un descuido: es una tolerancia deliberada y testeada
(`tests/test_router_config.py`, `test_existing_routing_rules_are_still_validated`
y `test_existing_config_with_routing_rules_remains_valid`), puesta para no
romper configuraciones de operador en mitad de la linea del router. Lo que nunca
se decidio es CUANDO termina.

Lo que cuesta mantenerla es del peor tipo: una clave que el operador puede
escribir, que `config.validate` acepta y bendice, y que el motor ignora en
silencio. La configuracion parece decir algo que no dice.

## Cambio

Retirar `routing_rules` del esquema por completo, con rechazo TIPADO:

- `validator.py`: una config con `routing_rules` en cualquier dominio falla con
  `ConfigError`, `field=routing_rules`, y mensaje accionable: el enrutado es
  semantico, declara `router` y describe cada dominio en su `description`.
- `schema.py` y `loader.py`: `DomainConfig` deja de tener el campo.
- `tests/test_router_config.py`: los dos tests de tolerancia se invierten (pasan
  a asertar el rechazo).
- Fixtures que aun la traen: se limpian (`eval/fixtures/config.yaml`,
  `eval/fixtures/orchestration*.yaml`, `eval/battery/conformance.yaml`,
  `eval/battery/v0.3/presupuesto_y_esfuerzo.yaml`, y las de tests que la usen).
  Las plantillas de `config/` ya no la traen.

Por que rechazo y no aviso: dar un canal de warnings a `config.validate`
-que hoy devuelve `{"status": "ok"}` y nada mas- seria inventar superficie de
contrato PERMANENTE para gestionar un transitorio. Un error que se lee una vez y
se arregla borrando dos lineas es mas barato que un silencio que no se detecta
nunca.

Por que ahora: romper contrato de config es MINOR, y la linea v0.4 ya se corta
como MINOR. Hacerlo aqui cuesta cero en version; aplazarlo obliga a esperar al
siguiente MINOR, sin fecha.

## Criterios de aceptacion

- Una config con `routing_rules` en un dominio falla en `config.validate` con
  `ConfigError` y `field=routing_rules`, por CLI, REST y MCP.
- El mensaje de error nombra la alternativa (`router` y `description`), no solo
  el problema.
- Una config sin `routing_rules` se comporta exactamente como hoy: enrutado
  semantico, precedencia intacta.
- `DomainConfig` no expone `routing_rules`; nada en `src/` la referencia.
- Las plantillas de `config/` siguen validando.
- Digest de conformance: se espera INTACTO, porque la clave no influye en
  ningun resultado; si se moviera, hay que recalcularlo y DECLARARLO
  (ADR 0017) antes de dar la ficha por implementada.
- pytest en verde con y sin extras.

## Archivos previstos

- `src/ianest_core/config/schema.py`
- `src/ianest_core/config/loader.py`
- `src/ianest_core/config/validator.py`
- `tests/test_router_config.py` (y las demas que la usen)
- fixtures de `eval/`
- `CHANGELOG.md`

## No cubre

- Migracion automatica de configuraciones existentes: la accion es borrar la
  clave, y hacerlo por el operador significaria reescribirle su fichero.
- Un canal de warnings en `config.validate` (descartado arriba).
- Cualquier otra clave del esquema: esta ficha ejecuta ADR 0043 y nada mas.

## Resultado

Implementada. `DomainConfig` pierde el campo, `loader.py` deja de leerlo y
`validator.py` rechaza la clave con `ConfigValidationError`,
`field="routing_rules"`, y un mensaje que nombra `router` y `description`. El
rechazo se comprueba antes que los campos obligatorios del dominio, de modo que
una config heredada recibe primero el motivo que la explica.

Los dos tests que fijaban la tolerancia pasan a asertar el rechazo, con dos
anadidos: mapa vacio tambien rechazado (la clave entera, no su contenido) y el
mensaje mencionando la alternativa. Limpiados los siete fixtures y los tres
tests que la construian a mano.

Verificado de forma independiente: pytest 237 con extras y 233 mas 4 skips sin
extras; las dos plantillas de `config/` validan; `grep` no encuentra
`routing_rules` fuera del rechazo y sus tests. **Digest de conformidad intacto**
(`6b7067ef...`), como se esperaba: la clave no influia en ningun resultado.

Nota de proceso: el brief de la tarea cito como esperado el digest `6dcae1a5`,
que es el historico de 42 casos de la linea del router; el vigente es
`6b7067ef` con 81. El implementador lo detecto y lo dijo en vez de ajustar el
numero, que es el comportamiento correcto.
