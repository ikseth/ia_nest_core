# Decision 0024: instalacion y deteccion de runtime/GPU (fase 9)

Fecha: 2026-07-11

## Decision

- Instalacion: script bash `install.sh` que crea un venv (Python 3.13) e
  instala el core (`pip install -e .`), con los extras de interfaz
  (`.[interfaces]`) opcionales (bajo flag).
- Deteccion de runtime/GPU: LOCAL. GPU via `nvidia-smi` si existe; runtime
  (version de Python/plataforma); alcance del backend (endpoint
  OpenAI-compatible reachable, reutiliza `AvailabilityProvider`). Se integra
  en `runtime.health` (mejora el `_gpu_status` actual) y se accede por
  `ianest runtime detect`.
- No se consulta el host remoto por SSH (regla de no conectar sin permiso);
  la deteccion de GPU es local.

## Motivo

bash es idiomatico y minimo para el bootstrap de entorno; centralizar la
deteccion en `runtime.health` evita dos fuentes de verdad. Repo publico: sin
datos internos; endpoints por variable de entorno.

## Consecuencia

- `runtime.health` reporta deteccion real de GPU (nvidia-smi) y runtime,
  ademas del alcance del backend.
- La GPU del host de laboratorio (remoto) no se detecta directamente;
  `runtime.health` refleja la GPU local y el alcance del backend.
- Scripts no triviales con cabecera humana/IA (CONVENCIONES).
