# Handoff de implementacion: fase 9 (instalacion y deteccion de runtime/GPU)

Destinatario: agente codificador (Codex/Sonnet).
Autor: Claude Code (Opus), rol disenador.
Verificacion: Opus.
Base: `main` con fases 1-8 integradas y verificadas. Fase mecanica; reutiliza
`runtime.health` (fase 7) y `AvailabilityProvider` (6b).

## Objetivo

Cerrar el ultimo punto del checklist "core cerrado" de
`IA_NEST_CORE_CONTEXT.md`: instalacion reproducible + deteccion de
runtime/GPU. Decisiones en el ADR 0024.

## Dentro de fase 9

1. `install.sh` (bash, ADR 0024):
   - Crea un venv con Python 3.13 e instala el core (`pip install -e .`).
   - Con un flag (p.ej. `--interfaces`) instala tambien los extras
     `.[interfaces]` (mcp, starlette, uvicorn).
   - Idempotente, con mensajes claros y salida de error util.
   - Cabecera humana/IA (proposito, entradas, salidas, efectos, requisitos,
     seguridad) segun `CONVENCIONES.md`.
2. Deteccion de runtime/GPU (ADR 0024), mejorando `service.health`:
   - GPU: usar `nvidia-smi` si esta disponible (nombre, memoria); si no,
     `available: false`. Best-effort: no romper si falta.
   - runtime: version de Python y plataforma.
   - backend: alcance del endpoint OpenAI-compatible (reutiliza el probe /
     `AvailabilityProvider`, ya presente).
   - Exponer por `ianest runtime detect` (subcomando que imprime la deteccion;
     puede compartir logica con `runtime.health`). Sin SSH al host remoto:
     deteccion local.
3. Documentar la instalacion (README o `docs/`): pasos desde cero, extras
   opcionales, `.env` a partir de `.env.example`.

## Fuera de fase 9 (NO implementar)

- Gestion de secretos productiva, publicacion a PyPI, contenedores (se
  adoptaran imagenes existentes si hace falta, ADR 0009, pero no aqui).
- Consultar la GPU del host remoto por SSH.

## No reinventar (ya fijado)

- `runtime.health` (fase 7) y `AvailabilityProvider` (6b).
- Capa de servicio y paridad; extras opcionales de interfaz (ADR 0021).

## Blanco de aceptacion

- `install.sh` instala el core desde cero en un venv limpio y `pytest` pasa
  (12 passed, 2 skipped sin extras); con `--interfaces`, instala los extras y
  `pytest` da 19 passed.
- `runtime.health` / `ianest runtime detect` reporta GPU (via `nvidia-smi` si
  hay; en esta maquina `available: false`) y runtime, sin romper cuando no hay
  GPU.
- Scripts con cabecera; sin datos internos versionados; endpoints por env var.
- `pytest` en verde.

## Restricciones y convenciones

- Python 3.13; pip + venv; pytest. Codigo en ingles snake_case; scripts bash
  con nombres claros; prosa/comentarios en espanol sin tildes.
- Repo PUBLICO: nada interno en archivos versionados. Corres en esta maquina:
  puedes probar `install.sh` en un venv temporal; NO conectes al host de
  laboratorio.
- Ambiguedad o contradiccion en los docs -> PARA y preguntame.

## Entrega y handoff de vuelta

Rama nueva desde `main` (p.ej. `fase-9-install-detect`), tests en verde, y una
nota de las decisiones tomadas. Opus verifica: instalacion desde cero en venv
limpio (con y sin extras) y la deteccion de runtime/GPU.
