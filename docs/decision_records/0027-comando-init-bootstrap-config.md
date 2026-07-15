# Decision 0027: comando `ianest init` para bootstrap de configuracion

Fecha: 2026-07-15

## Decision

Anadir un subcomando `ianest init` que genera la configuracion inicial:

    ianest init [--endpoint URL] [--template minimal|lab] [--force]

- Genera `config/core.yaml` copiando una plantilla: `minimal` ->
  `config/core.example.yaml` (por defecto); `lab` ->
  `config/core.lab.example.yaml`.
- Genera `.env` con `OPENAI_COMPAT_BASE_URL=<endpoint>`. Si no se pasa
  `--endpoint`, lo pregunta por stdin con default `http://localhost:11434/v1`.
- No sobrescribe `config/core.yaml` ni `.env` si ya existen, salvo `--force`.
- Tras generar, valida la config y reporta `ok` o el error (limpio).

## Motivo

Crear `config/core.yaml` y `.env` a mano es propenso a errores (variable
equivocada, formato, puerto), como se vio en el dogfooding. Un comando
asistido elimina esa friccion de onboarding. Es configuracion declarativa
asistida, dentro del alcance (scripts de instalacion/configuracion).

## Consecuencia

- Nuevo subcomando en la CLI; reutiliza las plantillas existentes y la
  validacion; no toca el nucleo.
- Se documenta en el manual de usuario (instalacion.md / configuracion.md).
