# Decision 0050: el ente provisiona su backend desde el INSTALADOR, no desde el contrato

Fecha: 2026-08-15
Estado: reconciliado por el usuario (2026-08-15), sin puntos abiertos
Responde a: `ia_nest_meta/docs/handoff/independencia_del_entorno_del_ente.md`
Depende de: ADR 0003 (protocolo compatible con OpenAI), ADR 0028 (estrategia de
recursos de backend), ADR 0029 (provisioning de modelos), ADR 0024 (instalacion)

## Contexto

`ia_nest_extended` emitio un aviso duradero tras verificar en laboratorio: el
ente depende, para su backend de modelos, de una instalacion **anterior y ajena,
marcada para retirar**. El core apunta ahi su endpoint y la capa de
enriquecimiento apunta ahi sus embeddings. No es una dependencia de una capa: es
del ente entero, y retirar esa instalacion sin un paso de desacople deja a los
dos sin modelos a la vez.

El aviso pide una postura, no una capacidad: **si el ente debe traer su propio
backend por defecto**, manteniendo el endpoint configurable para quien quiera
apuntar a uno existente.

## Lo que ya existe, y que esta decision hace explicito

La respuesta esta a medias en el repo, sin registrar:

- `deploy/ollama.compose.yaml` declara el backend con GPU, y su cabecera avisa de
  que NO forma parte del core.
- `deploy/setup.sh` lo levanta, espera a que responda, descarga los modelos,
  instala el core, lo configura y verifica con una inferencia real.

Es decir: el ente ya sabe traerse su backend. Lo que falta no es codigo, es
**doctrina**. Hoy esa postura vive en un script y en un comentario, y la pregunta
"es el ente autonomo?" se responde leyendo `deploy/`. Eso es exactamente lo que
el aviso pedia que no ocurriera.

## Decision

**Independiente por defecto, personalizable por opcion.**

1. El ente **provisiona su propio backend de modelos** como parte de su
   INSTALACION. Es la ruta por defecto: una maquina limpia acaba con backend
   propio y modelos descargados, sin depender de nada anterior.
2. Quien tenga un backend y quiera usarlo, lo declara y la instalacion no lo
   toca. Sigue siendo un endpoint configurable, como hasta hoy.
3. **El CONTRATO no cambia.** El core sigue siendo agnostico (ADR 0003): declara
   un adaptador compatible con OpenAI y un endpoint, y no sabe si al otro lado
   hay un contenedor, un servicio del sistema o una maquina remota.

### Por que instalar no es una capacidad

Es la distincion que sostiene toda la decision, y conviene dejarla escrita en vez
de darla por supuesta:

- Una **capacidad** es algo que el core hace cuando alguien se lo pide, esta en
  `CORE_CONTRACT.md`, tiene contrato versionado y prueba de aceptacion.
- **Instalar** ocurre una vez, antes de que el core exista como proceso, y no lo
  invoca ningun consumidor. No entra en el contrato, no sube version del
  contrato, y no lo ejecuta el core: lo ejecuta un operador.

Por eso provisionar el backend desde el instalador NO roza la frontera del
agnosticismo, aunque provisionarlo desde una capacidad si lo haria.

### Lo que esta decision NO autoriza

- El core **no gestiona el ciclo de vida** del backend en ejecucion: no lo
  arranca, no lo reinicia si cae, no lo apaga. Si el backend no responde, el core
  lo reporta y devuelve error tipado, como hoy.
- El paquete del core **no aprende Docker**. El compose y el script viven en
  `deploy/`, fuera del paquete instalable, y el core minimo sigue instalandose
  sin ellos.
- No se decide aqui el backend de la capa de enriquecimiento (su almacen ya lo
  provisiona ella).

## Orden de migracion

El aviso lo fija y no se negocia, porque el riesgo es quedarse sin modelos a
mitad:

1. Desacoplar: backend propio del ente, con los modelos que hoy se usan.
2. Reapuntar la configuracion del core y la de la capa de enriquecimiento.
3. Verificar: salud del runtime, una inferencia real y una recuperacion de
   memoria de extremo a extremo.
4. Solo entonces, archivar la instalacion previa.

## Alternativas descartadas

- **Que el backend sea siempre infraestructura del operador.** Es lo que hay hoy
  de facto, y es justo lo que produjo el problema: el ente heredo una instalacion
  ajena y quedo atado a ella sin que nadie lo decidiera.
- **Que el core provisione el backend como CAPACIDAD** (`backend.up` o similar).
  Mete al core en el negocio de orquestar contenedores, le exige conocer Docker y
  contradice ADR 0003. Ademas obligaria a versionar bajo SemVer algo que solo se
  usa una vez por maquina.
- **Que el instalador provisione siempre, sin escapatoria.** Rompe a quien ya
  tiene un backend servido y solo quiere apuntar a el. La opcion de saltarlo ya
  existe y se conserva.

## Consecuencia

- `docs/DESPLIEGUE.md` deja de documentar solo el camino manual y presenta la
  instalacion desde cero como la ruta por defecto.
- Ficha del instalador declarativo: fichero de configuracion, personalizacion y
  verificacion (ficha v0.4/0003).
- Se responde al aviso en `ia_nest_meta/docs/handoff/`, y con ello queda cerrado.
- Impacto de version: **ninguno sobre el contrato**. Es doctrina e instalador;
  `CORE_CONTRACT.md` no cambia. Lo que cambie el instalador va como patch.
