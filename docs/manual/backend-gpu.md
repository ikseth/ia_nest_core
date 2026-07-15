# Backend con GPU (Ollama en Docker)

El core es agnostico al backend: habla a un endpoint OpenAI-compatible. Esta
guia despliega el backend recomendado -Ollama en Docker con GPU-, de forma
compartimentada y reproducible (ADR 0028). Ollama nativo en el host tambien
vale; el core no cambia.

## Requisitos del host

- Driver NVIDIA (comprueba: `nvidia-smi`).
- NVIDIA Container Toolkit (comprueba: `nvidia-ctk --version`). Tras instalarlo:
  `sudo nvidia-ctk runtime configure --runtime=docker` y
  `sudo systemctl restart docker`.

## Arrancar Ollama con GPU

    docker compose -f deploy/ollama.compose.yaml up -d

(La reserva de GPU del compose equivale a `docker run --gpus=all`.)

## Descargar modelos

    docker exec ia_nest_ollama ollama pull qwen2.5:7b
    docker exec ia_nest_ollama ollama pull mistral-nemo

## Verificar que USA la GPU

    docker exec ia_nest_ollama nvidia-smi -L          # ve la GPU?
    curl -s localhost:11434/api/ps                     # size_vram > 0 al cargar un modelo
    ianest --config config/core.yaml runtime detect    # GPU detectada + backend

## Caveat importante (daemon-reload)

Un `systemctl daemon-reload` del host (p.ej. al instalar servicios systemd)
puede resetear el cgroup de dispositivos y el contenedor **pierde la GPU**:
`nvidia-smi` dentro del contenedor da `Failed to initialize NVML: Unknown
Error` y Ollama cae a **CPU en silencio** (latencia alta). Solucion:

    docker restart ia_nest_ollama

Comprueba el estado real en cualquier momento con `ianest runtime detect`.
