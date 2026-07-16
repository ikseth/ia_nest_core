# 0001: ayuda CLI jerarquica

Estado: implementada
Tipo: mejora compatible
Impacto de version: patch
Version objetivo: v0.1.x

## Problema

La CLI admite `--help` en cada nivel, pero los grupos, acciones y opciones no
tienen descripciones suficientes. El usuario ve una lista de nombres sin el
detalle necesario para descubrir su funcion desde la linea de comandos.

## Cambio

Anadir ayuda descriptiva en los tres niveles:

- `ianest --help`
- `ianest GRUPO --help`
- `ianest GRUPO ACCION --help`

La ayuda raiz funciona como indice breve; la ayuda de grupo describe sus
acciones; la ayuda de accion explica opciones, valores por defecto, precedencia
y ejemplos relevantes. No se modifican nombres, argumentos ni comportamiento
operativo.

## Criterios de aceptacion

- Todos los grupos y acciones describen su finalidad.
- Todos los argumentos tienen una explicacion.
- La ayuda documenta la precedencia de modelo, dominio y router.
- La ayuda se obtiene sin cargar la configuracion ni contactar con el backend.
- Los comandos existentes mantienen su comportamiento.
- La suite de pruebas permanece en verde.

## Archivos previstos

- `src/ianest_core/cli.py`
- `tests/test_cli_help.py`
- `docs/manual/cli.md`
- `CHANGELOG.md`

## Resultado

Implementada ayuda descriptiva en la raiz, los siete grupos con acciones y las
doce acciones existentes. Las opciones comunes se definen mediante helpers
internos para evitar divergencias. La carga de `.env` se realiza despues del
parseo, por lo que `--help` no inicializa el entorno ni carga configuracion.

Se actualizaron el manual y `CHANGELOG.md`. Verificacion:

    PYTHONPATH=src python3 -m pytest -q
    57 passed, 2 skipped
