# 0003: instalador declarativo, con fichero de configuracion y personalizacion

Estado: propuesta (revision 2 - 2026-08-18)
Tipo: mejora del instalador (no toca contrato publico)
Impacto de version: patch
Version objetivo: v0.4.x

Revision 2: incorpora las decisiones del usuario del 2026-08-17 y tres hallazgos
del montaje real del laboratorio. Los puntos que siguen ABIERTOS estan marcados
como tales al final; no se dan por acordados.

## Problema

`deploy/setup.sh` ya hace la cadena completa -backend con GPU, modelos, core
instalado, configurado y verificado-, pero se queda corto para lo que se le va a
pedir: levantar entidades en maquinas virtuales de forma repetible.

Ocho huecos concretos. Los cinco primeros venian de la revision 1; los tres
ultimos salieron de montar el laboratorio de verdad.

1. **Toda la personalizacion va por banderas.** Para reproducir una instalacion
   hay que recordar la linea de comandos exacta, que es justo lo que un fichero
   evita.
2. **Los modelos se declaran dos veces**: en `--models` (lo que se descarga) y en
   `config/core.yaml` (lo que el core usa). Nada garantiza que coincidan. Y
   existe `ianest model pull`, que descarga los DECLARADOS: la fuente unica ya
   esta y el script no la usa.
3. **No se puede elegir la interfaz de escucha.** Los units systemd fijan
   `--host 127.0.0.1`, y hay que editarlos a mano despues de instalar.
4. **Los servicios quedan a medias.** `install.sh --service` genera los units,
   pero nadie los habilita ni los arranca, y `setup.sh` ni siquiera pasa
   `--service`.
5. **La verificacion avisa pero no falla.** En una instalacion desatendida, un
   smoke que no pasa tiene que poder devolver error.
6. **El nombre de proyecto de compose se hereda del DIRECTORIO.** Verificado en
   laboratorio: lanzar `deploy/ollama.compose.yaml` desde `/opt/ia_nest/resources/ollama`
   creo el volumen `ollama_ollama_models`. Ejecutar el mismo compose desde otra
   ruta crea un volumen DISTINTO y vacio, o sea que los modelos "desaparecen" sin
   que nada falle. No es hipotetico: el `ollama-backend.service` que habia en el
   host de laboratorio pasaba `--project-name` explicitamente, senal de que
   alguien ya tropezo con esto.
7. **`python3.13 -m venv` falla en un openSUSE minimo sin `python313-pip`**,
   porque `ensurepip` no encuentra su rueda. `install.sh` se rompe en su primera
   linea util y parece un fallo del script.
8. **`install.sh` exige `python3.13` EXACTO.** En una distribucion rolling ese
   binario cambia de nombre cada pocos meses, y la instalacion se rompera sola
   algun dia sin que nadie haya tocado nada.

Ademas `docs/DESPLIEGUE.md` documenta el camino manual y **no menciona
`deploy/setup.sh`**, que solo aparece en el manual de instalacion.

## Cambio

### 1. Fichero de configuracion PLANO, y argumentos que sobreescriben

`setup.sh` acepta `--config RUTA` con un fichero **plano `CLAVE=VALOR`**, no
YAML. Precedencia, que es la regla de siempre de este repo:

    argumento de linea de comandos  >  fichero  >  valor por defecto

**Por que plano y no YAML**, que era lo que proponia la revision 1: `setup.sh` es
bash, y el fichero hay que leerlo ANTES de que exista el venv -decide si se
provisiona el backend, los puertos, la interfaz y los servicios-. Leer YAML ahi
obliga a depender de PyYAML en el python del sistema, que en una instalacion
minima no esta garantizado. Un script de shell leyendo un fichero de shell no
necesita nada. El anidamiento que se perdia era de dos niveles y se resuelve con
prefijos.

    INSTANCE_NAME=core
    ENDPOINT=http://localhost:11434/v1
    TEMPLATE=lab
    CORE_CONFIG=
    PROVISION_BACKEND=true
    REST_HOST=127.0.0.1
    REST_PORT=8000
    MCP_HOST=127.0.0.1
    MCP_PORT=8090
    SERVICE_INSTALL=true
    SERVICE_ENABLE=false
    VERIFY=strict

**Claves desconocidas: rechazo tipado con mensaje accionable.** Precedente
inequivoco del repo (ADR 0043 y la retirada de `routing_rules`): una clave que el
validador bendice y el motor ignora es un bug. Esto ademas convierte en ruidoso
el error de pasarle a `setup.sh` el `config/core.yaml` del core por confusion con
el `--config` de `ianest`, que significa otra cosa.

`SERVICE_INSTALL=false` con `SERVICE_ENABLE=true` es contradictorio: error, no
arreglo silencioso.

**El fichero efectivo NO se versiona.** Se versiona la plantilla
(`deploy/ejemplo.setup.conf`); el efectivo lleva direcciones e identificadores de
una instalacion concreta y vive en `local/`, ya ignorado en bloque (convencion
transversal 5).

### 2. Los modelos salen de la config del core

Se retira `--models` como fuente. Tras escribir la configuracion, el instalador
ejecuta `ianest model pull`, que descarga los modelos DECLARADOS (ADR 0029). Una
sola lista, la que el core va a usar de verdad.

Si el proveedor declarado no soporta provisioning, `ianest model pull` **falla**
(`provisioner_for` devuelve `None` y `service.pull_models` lanza
`ProvisioningError`), y el instalador falla con el. Es la decision del usuario:
un descuido tiene que doler. La escapatoria para quien apunte a un backend ya
servido queda como punto ABIERTO al final de esta ficha.

### 3. `CORE_CONFIG`: instalar una configuracion afinada

`ianest init` solo copia una plantilla: escribe `config/core.yaml` y `.env` con
rutas fijas y **no acepta un fichero de origen** (`cli.py`, `_init`). Por eso la
promesa "una instalacion se reproduce con un fichero" no alcanza a una
instalacion con modelos y dominios ya afinados, que es justo la nuestra.

`CORE_CONFIG=<ruta>`, excluyente con `TEMPLATE`: el instalador **copia** esa
configuracion a la ubicacion efectiva, escribe el `.env` con el endpoint y
ejecuta `config.validate` en vez de `ianest init`. Con eso, una instalacion
completa se reproduce con dos ficheros bajo `local/`: el plano del instalador y
el `core.yaml` afinado. No cambia el contrato de `init`.

### 4. `INSTANCE_NAME`

Nombra la instalacion, con dos efectos y ninguno magico:

- los units pasan a `ianest-<instancia>-rest.service` y `ianest-<instancia>-mcp.service`,
  para que dos entidades convivan en una maquina sin pisarse;
- el resumen final del instalador lo muestra.

Por defecto, `core`. **Consecuencia declarada**: los units de hoy se llaman
`ianest-rest.service` y `ianest-mcp.service`, asi que con el defecto `core` pasan
a llamarse distinto para todo el mundo. La revision 1 prometia a la vez que "sin
`--config`, el comportamiento es el de hoy"; esas dos cosas no pueden ser ciertas
juntas y **manda el nombre**. La ficha declara el renombrado y `DESPLIEGUE.md`
lleva su linea de migracion: parar y deshabilitar los units viejos antes de
reinstalar. Coste real bajo: la unica instalacion afectada era la del laboratorio,
ya retirada.

### 5. Interfaz de escucha configurable

`REST_HOST` y `MCP_HOST` llegan a los units. **El defecto sigue siendo
`127.0.0.1`**: abrir a la red es decision explicita del operador, no efecto de
instalar. El instalador avisa cuando se declara una interfaz no local, porque el
core no tiene autenticacion (`ia_nest_meta/docs/CAPAS_FUTURAS.md`).

### 6. `IANEST_CONFIG`: sacar la configuracion del clon

Para que la configuracion efectiva sobreviva a un re-clon hace falta que viva
fuera del arbol de git. Hoy no puede: el unit REST arranca
`uvicorn --factory ianest_core.rest:create_app`, y **una factoria de uvicorn no
admite argumentos**, asi que `create_app` no puede recibir la ruta; su defecto es
la ruta RELATIVA `config/core.yaml`, resuelta contra `WorkingDirectory`. MCP si
acepta `--config`. Es una asimetria entre interfaces.

`rest.py` lee `IANEST_CONFIG` del entorno como defecto, y el unit la pasa por su
`EnvironmentFile`. Son unas pocas lineas, cierran la asimetria y desbloquean la
distribucion de directorios de abajo.

### 7. Distribucion de directorios en la maquina del ente

    /opt/ia_nest/repositories   clones de git
    /opt/ia_nest/config         configuracion efectiva y .env, por instancia
    /opt/ia_nest/state          telemetria y logs

Separar codigo, configuracion y estado es lo que hace que rehacer una entidad
desde cero sea barato: un `rm -rf` del clon no se lleva ni la configuracion
afinada ni el historico de telemetria. En el anfitrion de un laboratorio con
virtualizacion, `/opt` es de las maquinas virtuales y los contenedores; esta
distribucion es la de DENTRO de la maquina del ente.

### 8. Nombre de proyecto de compose fijo

El compose declara su `name:`, para que el nombre del volumen no dependa del
directorio desde el que se lance. Va en el fichero y no en la linea de comandos:
asi viaja con el compose y no hay que recordarlo.

### 9. Requisitos de python

- `install.sh` acepta **`>= 3.13`** en vez de exigir `3.13` exacto, y lo dice en
  su mensaje de error.
- La documentacion de despliegue declara `python313-pip` -o su equivalente- como
  requisito, porque sin el `python3.13 -m venv` no funciona.

### 10. Servicios y verificacion

- Con `SERVICE_ENABLE=true`, el instalador habilita y arranca los units, y
  comprueba que responden.
- `VERIFY=strict` hace que un smoke fallido devuelva codigo distinto de cero.
  `warn` conserva el comportamiento de hoy. `skip` no verifica.
- La verificacion lee **`backend.gpu` de `runtime.health`** (ADR 0049) y avisa si
  el backend no esta usando la GPU. Con eso, `warn_if_backend_uses_cpu` de
  `deploy/setup.sh` **se BORRA**: era un prototipo en bash que ademas estaba mal
  condicionado -solo corria si el propio script levantaba el backend, o sea nunca
  en la topologia con backend remoto- y apuntaba a `localhost` fijo.

### 11. Documentacion

`docs/DESPLIEGUE.md` presenta la instalacion desde cero (`deploy/setup.sh`) como
ruta por defecto y el camino manual como alternativa, con ejemplo de fichero de
configuracion sin datos de ninguna instalacion real, la linea de migracion de los
units y el requisito de `python313-pip`.

## Criterios de aceptacion

- Una instalacion completa se reproduce con `bash deploy/setup.sh --config
  ejemplo.conf`, sin mas argumentos.
- Un argumento sobreescribe el valor del fichero, y el fichero sobreescribe el
  defecto; verificado con al menos un campo de cada tipo.
- Una clave desconocida en el fichero se rechaza con mensaje accionable.
- `SERVICE_INSTALL=false` con `SERVICE_ENABLE=true` es error.
- Sin `--config`, el comportamiento es el de hoy **salvo el nombre de los units**,
  que cambia por el defecto `INSTANCE_NAME=core` y esta declarado.
- Los modelos descargados son exactamente los declarados en la configuracion del
  core, y con proveedor sin provisioning la instalacion FALLA.
- Con `CORE_CONFIG`, la configuracion instalada es identica byte a byte a la
  suministrada, y `ianest model pull` descarga sus modelos.
- El servicio REST arranca con su configuracion FUERA del clon, via
  `IANEST_CONFIG`.
- Con `SERVICE_ENABLE=true`, `systemctl is-active` da verde para los dos units y
  responden en su puerto.
- Con `VERIFY=strict` y un endpoint roto, el instalador sale con codigo distinto
  de cero.
- Instalar con `REST_HOST` no local emite el aviso de ausencia de autenticacion.
- El volumen de modelos conserva su nombre al lanzar el compose desde otra ruta.
- `install.sh` acepta python 3.14 sin tocarlo.
- `warn_if_backend_uses_cpu` ya no existe.
- `docs/DESPLIEGUE.md` no describe pasos que el script ya hace.
- Sin dependencias nuevas. Todo en ASCII.

## Archivos previstos

- `deploy/setup.sh`, `install.sh`, `deploy/ollama.compose.yaml`
- `deploy/ejemplo.setup.conf` (plantilla, sin datos reales)
- `src/ianest_core/rest.py` (lectura de `IANEST_CONFIG`)
- `docs/DESPLIEGUE.md`, `docs/manual/instalacion.md`
- `CHANGELOG.md`

## Puntos ABIERTOS, pendientes del usuario

1. **Escapatoria del pull.** Con la decision de fallar, quien apunte a un backend
   ya servido con un proveedor sin provisioning no puede instalar. Se propuso
   `MODELS=pull|skip` -defecto `pull`, para que el descuido siga fallando y la
   decision consciente tenga salida- y no consta acordado.
2. **`INSTANCE_NAME` de nuestro despliegue.** El defecto es `core`. Para el
   laboratorio quedo sin fijar; conviene que no coincida con el nombre de la
   maquina anfitriona para no confundir dos cosas distintas.

## No cubre

- Bastionado, cortafuegos, VLANs o backups: infraestructura del operador.
- Autenticacion de las interfaces: concern registrado en
  `ia_nest_meta/docs/CAPAS_FUTURAS.md`, y no se resuelve con una bandera de
  instalador.
- Instalar drivers NVIDIA, Docker o el toolkit de contenedores.
- La capa de enriquecimiento: su instalacion es de su repo.
- El coste de `runtime.health` con el backend caido, que es
  [ficha v0.4/0004](0004-salud-lenta-con-el-backend-caido.md).

## Resultado

Pendiente.
