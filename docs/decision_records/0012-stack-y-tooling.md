# Decision 0012: stack y tooling del proyecto

Fecha: 2026-07-10

## Decision

- Lenguaje: Python 3.13 (version del sistema y de la cantera ia_nest).
- Aislamiento y dependencias: venv + pip.
- Metadatos y dependencias declaradas en `pyproject.toml` (PEP 621),
  instalable con `pip install -e .`.
- Tests: pytest.
- Sin linter, formatter ni type-checker por ahora.

## Motivo

Preferencia del usuario por lo minimo y estandar, coherente con la filosofia
UNIX y la regla de no anadir abstracciones ni herramientas sin necesidad
demostrada. Python 3.13 evita friccion con el entorno existente.

## Consecuencia

- Layout src (`src/ianest_core/`) ya presente; tests en `tests/`.
- `pyproject.toml` es metadata minima de paquete que pip lee, no una
  herramienta adicional.
- La calidad se sostiene con tests + revision humana/IA, no con
  type-checking automatico.
- Revision tras la primera implementacion: si aparecen inconsistencias de
  nombres o estilo que la revision manual no baste para contener, se
  reconsiderara anadir linter/formatter/type-checker (ruff/pyright). Esto
  atiende la tension con la regla de nombres normalizados de
  `CONVENCIONES.md`.
- No se introducen uv/poetry: pip+venv basta para el alcance actual.
