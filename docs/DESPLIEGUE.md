# Despliegue y validacion en laboratorio

Guia generica para desplegar el core en un host con GPU y validar el smoke
real contra un backend OpenAI-compatible (p.ej. Ollama).

Trazabilidad: esta guia es publica y generica. Los detalles concretos del
entorno (IPs, hosts, salidas de ejecucion) NO van aqui: viven en `local/`
(no versionado). Ver "Registro de ejecuciones".

## Requisitos del host

- Python 3.13 y git.
- GPU CUDA (~12 GB VRAM para un modelo 7-8B cuantizado).
- Backend OpenAI-compatible corriendo (p.ej. Ollama) con un modelo descargado.

## Pasos

1. Clonar (repo publico, sin credenciales):

   ```
   git clone https://github.com/ikseth/ia_nest_core.git
   cd ia_nest_core
   ```

2. Instalar con interfaces (crea venv, instala core + extras MCP/REST):

   ```
   bash install.sh --interfaces
   source .venv/bin/activate
   ```

3. Backend: asegurar el modelo y el endpoint (p.ej. `ollama pull llama3.1:8b`).

4. Configurar (sin secretos en YAML; endpoint por env var):

   ```
   cp config/core.example.yaml config/core.yaml    # ajustar model_name si aplica
   cp .env.example .env                            # poner OPENAI_COMPAT_BASE_URL
   # p.ej. OPENAI_COMPAT_BASE_URL=http://localhost:11434/v1
   ```

5. Detectar runtime/GPU (debe ver la GPU del host):

   ```
   ianest --config config/core.yaml runtime detect --json
   ```

6. Smoke real:

   ```
   ianest --config config/core.yaml prompt run --prompt "Explica en una frase que es un sistema operativo." --domain general
   ianest --config config/core.yaml eval run --track smoke --json
   ```

## Registro de ejecuciones (trazabilidad)

Las ejecuciones concretas (host, comandos, salidas, fecha) se registran en
`local/lab/` (no versionado), para trazabilidad sin exponer datos internos
en el repo publico. Un resumen saneado (que se probo, pass/fail, ajustes
aplicados) puede reflejarse en `docs/PLAN.md` (fase de validacion).
