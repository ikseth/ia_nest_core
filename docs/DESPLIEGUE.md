# Despliegue

La ruta por defecto instala una entidad declarativa: backend propio, core,
configuracion, modelos y, si se activa, servicios. El camino manual queda para
quien ya administra un backend compatible con OpenAI.

Trazabilidad: esta guia es publica y generica. Los detalles concretos del
entorno (IPs, hosts, salidas) viven en `local/` y no se versionan.

## Ruta por defecto: instalacion desde cero

Requisitos del host:

- Python >= 3.13, git y el paquete de pip/ensurepip de esa version (por ejemplo,
  `python313-pip` en openSUSE).
- GPU CUDA (~12 GB VRAM para un modelo 7-8B cuantizado).
- Docker, driver NVIDIA y NVIDIA Container Toolkit. El instalador los comprueba,
  pero no los instala.

1. Clonar el repositorio:

   ```
   git clone https://github.com/ikseth/ia_nest_core.git
   cd ia_nest_core
   ```

2. Copiar y ajustar la plantilla. El fichero efectivo pertenece al operador y
   debe vivir fuera del repositorio, por ejemplo en `local/`:

   ```
   cp deploy/ejemplo.setup.conf local/core.setup.conf
   bash deploy/setup.sh --config local/core.setup.conf --print-config
   ```

   `--print-config` solo muestra valores y su origen (`default`, `file` o
   `argument`); no escribe, no usa Docker ni conecta a la red. La precedencia es
   argumento > fichero > defecto. Las claves desconocidas son error para no
   confundir este fichero plano con `core.yaml`.

3. Instalar:

   ```
   sudo bash deploy/setup.sh --config local/core.setup.conf
   ```

   El instalador crea o usa `/opt/ia_nest/repositories` para clones,
   `/opt/ia_nest/config/<instancia>` para `core.yaml` y `.env`, y
   `/opt/ia_nest/state/<instancia>` para el estado de los servicios. Descarga
   exactamente los modelos declarados en ese `core.yaml` mediante
   `ianest model pull`. Un proveedor sin provisioning hace fallar la instalacion.

   Con `SERVICE_ENABLE=true`, los units se habilitan y arrancan como
   `ianest-<instancia>-rest.service` e `ianest-<instancia>-mcp.service`.
   El nombre por defecto es `core`, por lo que los nombres anteriores
   `ianest-rest.service` e `ianest-mcp.service` cambian.

## Migracion de units anteriores

Antes de reinstalar una maquina con los nombres antiguos:

```
sudo systemctl disable --now ianest-rest.service ianest-mcp.service
```

## Ruta manual: backend ya administrado

Declara `PROVISION_BACKEND=false` y el endpoint de ese backend en el fichero de
setup. El instalador no lo inicia ni lo modifica, pero sigue validando la
configuracion, instalando el core y ejecutando `ianest model pull` contra los
modelos declarados.

`CORE_CONFIG=/ruta/core.yaml` copia una configuracion afinada byte a byte a la
ubicacion efectiva; en ese caso no declares `TEMPLATE`. La configuracion y el
endpoint efectivo se pasan a REST mediante `IANEST_CONFIG` y su `EnvironmentFile`,
por lo que los servicios no dependen de una ruta dentro del clon.

## Verificar por REST despues de actualizar

`deploy/setup.sh` verifica con la CLI, que lee del disco en cada invocacion. Un
servicio REST ya arrancado NO: sigue con el codigo que cargo en memoria, asi que
actualizar el arbol no lo actualiza. Y la REST es justo la superficie que
consumen las capas de encima, que hablan por red.

Por eso, tras actualizar el codigo de una maquina con servicios:

```
git pull                                    # SIN sudo, ver el aviso de abajo
sudo <clon>/.venv/bin/pip install -e . --no-deps
sudo systemctl restart ianest-<instancia>-rest.service ianest-<instancia>-mcp.service
python3 deploy/smoke_rest.py http://<host>:<puerto> --expect-version <version>
```

El `pip install` va con `sudo` porque el venv es de root a proposito: un servicio
no debe poder modificar su propio codigo. El `git`, NUNCA.

El smoke se EJECUTA y devuelve codigo de salida; no es una tabla que se redacta.
Comprueba la superficie -capacidades presentes, `/task/run` en JSON y
`/task/stream` en SSE, `backend.gpu` como lista y sin filtrar topologia- e
imprime las lineas del gate de tarea para que se lean. `--expect-version` es lo
que atrapa un proceso viejo: si el servicio declara otra version que la
instalada, el smoke falla en vez de dar por buena una verificacion que midio el
codigo anterior.

Reinstalar tambien hace falta para que `core_version` cambie: sale de los
metadatos del paquete instalado, no del arbol.

### Nunca lances `git` con `sudo` dentro del clon

Ni `install.sh` ni `deploy/setup.sh` invocan `git`: el clon lo mantiene el
operador. Si en algun momento se lanza `sudo git pull` -o cualquier otro `git`
como root-, todo lo que git escriba en esa pasada queda de root, y el clon entra
en un punto muerto del que no sale ningun usuario:

- el usuario normal no puede escribir `.git/FETCH_HEAD` porque es de root;
- `root` se niega con "posesion dudosa" porque el DIRECTORIO es del usuario, que
  es una proteccion de git contra ejecutar hooks ajenos y hace bien.

Se sale devolviendo el clon a su dueno, sin tocar el venv:

```
cd <clon>
sudo find . -path ./.venv -prune -o -user root -exec chown <usuario>:<grupo> {} +
```

Conviene mirar tambien el arbol de trabajo, no solo `.git`: un fichero versionado
que quedara de root hace fallar el siguiente `checkout` que lo toque.

## Registro de ejecuciones

Las ejecuciones concretas (host, comandos, salidas, fecha) se registran en
`local/lab/` (no versionado), para trazabilidad sin exponer datos internos en el
repo publico. Un resumen saneado puede reflejarse en `docs/PLAN.md`.
