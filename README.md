# IA_NEST Core

El motor del ente: recibe una peticion, decide que modelo la atiende y la
ejecuta. Todo local, con modelos que corren en tu maquina o en tu red.

## Que hace, en una pantalla

    prompt.run       responde a una pregunta con el modelo adecuado
    reasoning.run    razona por pasos, con limites de tiempo y de gasto
    task.plan        descompone una tarea en subtareas
    task.run         las ejecuta, reparte entre modelos y combina el resultado
    domain.route     decide a que dominio pertenece un texto, por sentido
    runtime.health   dice como esta todo, incluido si el backend usa la GPU
    capability.list  enumera lo que el core sabe hacer y como se invoca

Son 16 capacidades y las tres interfaces -linea de comandos, REST y MCP- ofrecen
exactamente las mismas. No hay funciones escondidas en una que falten en otra.

## Lo que NO hace, a proposito

Memoria, RAG, web, agentes, interfaz grafica y conciencia **no viven aqui**.
Cada una es su propio repositorio y habla con este por contrato. El core no las
conoce, y esa ignorancia es deliberada: es lo que impide que crezca sin freno.

## Como empezar

**Si vas a instalarlo o usarlo**, el manual: [docs/manual/](docs/manual/). La
instalacion desde cero, incluido su backend de modelos, esta en
[docs/DESPLIEGUE.md](docs/DESPLIEGUE.md).

**Si vas a cambiar algo**, dos documentos y en este orden:

1. [docs/CORE_CONTRACT.md](docs/CORE_CONTRACT.md) - que promete el core. Es la
   fuente de verdad de lo que hace y de la forma de sus respuestas.
2. [docs/PLAN.md](docs/PLAN.md) - en que fase esta cada linea de trabajo y cual
   es su criterio de salida.

Con esos dos se puede trabajar. El resto es profundidad, no requisito.

**Si te preguntas por que algo es como es**, mira
[docs/decision_records/](docs/decision_records/): una decision por documento, con
sus alternativas descartadas. No hace falta leerlos en orden ni todos; se
consultan cuando una decision concreta sorprende.

## Estado

Linea v0.4 completa en codigo, sin publicar todavia. La version del paquete
sigue en la anterior a proposito hasta que se corte el tag.

## Instalacion rapida

```bash
./install.sh --interfaces
source .venv/bin/activate
pytest
```

El script reutiliza `.venv` si ya existe. La configuracion real y los secretos no
se versionan: `cp .env.example .env` y rellenar con valores locales.

## Como se trabaja aqui

Reglas del repo en [docs/CONVENCIONES.md](docs/CONVENCIONES.md), y las que aplican
a todo el ente en el repositorio de gobernanza `ia_nest_meta`. Dos que conviene
saber antes de escribir nada:

- Los documentos van **sin acentos ni tildes**. Es deliberado y hay un test que
  lo comprueba.
- Cada cambio de comportamiento se acompana de un caso en la bateria de
  evaluacion, y esa bateria se congela ANTES de implementar. Es lo que impide que
  el criterio se ajuste para que pase la implementacion.
