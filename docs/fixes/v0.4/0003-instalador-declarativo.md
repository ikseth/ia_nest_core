# 0003: instalador declarativo, con fichero de configuracion y personalizacion

Estado: propuesta
Tipo: mejora del instalador (no toca contrato publico)
Impacto de version: patch
Version objetivo: v0.4.x

## Problema

`deploy/setup.sh` ya hace la cadena completa -backend con GPU, modelos, core
instalado, configurado y verificado-, pero se queda corto para lo que se le va a
pedir: levantar entidades en maquinas virtuales de forma repetible.

Cinco huecos concretos:

1. **Toda la personalizacion va por banderas.** `--endpoint`, `--template`,
   `--models`, `--rest-port`, `--mcp-port`. Para reproducir una instalacion hay
   que recordar la linea de comandos exacta, que es justo lo que un fichero
   evita.
2. **Los modelos se declaran dos veces**: en `--models` (lo que se descarga) y en
   `config/core.yaml` (lo que el core usa). Nada garantiza que coincidan. Y
   existe `ianest model pull`, que descarga los DECLARADOS: la fuente unica ya
   esta y el script no la usa.
3. **No se puede elegir la interfaz de escucha.** Los units systemd fijan
   `--host 127.0.0.1`. En una maquina virtual donde otra capa o el operador
   necesitan alcanzar el core, eso obliga a editar el unit a mano despues de
   instalar.
4. **Los servicios quedan a medias.** `install.sh --service` genera los units,
   pero nadie los habilita ni los arranca, y `setup.sh` ni siquiera pasa
   `--service`. Una VM recien instalada no queda lista.
5. **La verificacion avisa pero no falla.** En una instalacion desatendida, un
   smoke que no pasa tiene que poder devolver error, o no se sabra que la maquina
   quedo mal sin ir a mirarla.

Ademas `docs/DESPLIEGUE.md` documenta el camino manual y **no menciona
`deploy/setup.sh`**, que solo aparece en el manual de instalacion.

## Cambio

### 1. Fichero de configuracion, y argumentos que sobreescriben

`setup.sh` acepta `--config RUTA` con un YAML -formato ya usado por el core, sin
dependencias nuevas- con TODOS los valores, o parte de ellos. Precedencia, que es
la regla de siempre de este repo:

    argumento de linea de comandos  >  fichero  >  valor por defecto

Asi una instalacion se reproduce con un fichero, y una variante puntual -"la
misma pero con otra IP"- es un argumento, sin editar el fichero ni duplicarlo.

Campos previstos, todos opcionales:

    instance_name: laboratorio          # identifica esta instalacion
    endpoint: http://localhost:11434/v1
    template: lab                       # minimal | lab
    provision_backend: true             # false = usar un backend existente
    rest:
      host: 127.0.0.1
      port: 8000
    mcp:
      host: 127.0.0.1
      port: 8090
    service:
      install: true                     # generar units
      enable: false                     # habilitar y arrancar
    verify: strict                      # strict | warn | skip

### 2. Los modelos salen de la config del core

Se retira `--models` como fuente. Tras `ianest init`, el instalador ejecuta
`ianest model pull`, que descarga los modelos DECLARADOS en `config/core.yaml`
(ADR 0029). Una sola lista, la que el core va a usar de verdad.

Consecuencia buscada: es imposible acabar con un modelo descargado que la config
no usa, o con una config que declara un modelo que nadie descargo.

### 3. `instance_name`

Nombra la instalacion, con dos efectos y ninguno magico:

- los units systemd pasan a `ianest-<instance>-rest.service` y
  `ianest-<instance>-mcp.service`, de modo que dos entidades pueden convivir en
  una misma maquina sin pisarse;
- el resumen final del instalador lo muestra, para que quede claro que maquina
  es cual.

Por defecto, `core`. No entra en la configuracion del core ni en su contrato.

### 4. Interfaz de escucha configurable

`rest.host` y `mcp.host` llegan a los units. **El valor por defecto sigue siendo
`127.0.0.1`**: abrir a la red es una decision explicita del operador, no un
efecto de instalar. El instalador avisa cuando se declara una interfaz no local,
porque el core no tiene autenticacion (`ia_nest_meta/docs/CAPAS_FUTURAS.md`).

### 5. Servicios y verificacion

- Con `service.enable: true`, el instalador habilita y arranca los units, y
  comprueba que responden.
- `verify: strict` hace que un smoke fallido devuelva codigo de salida distinto
  de cero. `warn` conserva el comportamiento de hoy. `skip` no verifica.

### 6. Documentacion

`docs/DESPLIEGUE.md` presenta la instalacion desde cero (`deploy/setup.sh`) como
ruta por defecto, y el camino manual como alternativa. Ejemplo de fichero de
configuracion incluido, sin datos de ninguna instalacion real.

## Criterios de aceptacion

- Una instalacion completa se reproduce con `bash deploy/setup.sh --config
  ejemplo.yaml`, sin mas argumentos.
- Un argumento sobreescribe el valor del fichero, y el fichero sobreescribe el
  defecto; verificado con al menos un campo de cada tipo.
- Sin `--config`, el comportamiento es el de hoy: mismos defectos, mismas
  banderas.
- Los modelos descargados son exactamente los declarados en `config/core.yaml`.
- Con `service.enable: true`, `systemctl is-active` da verde para los dos units
  y responden en su puerto.
- Con `verify: strict` y un endpoint roto, el instalador sale con codigo distinto
  de cero.
- Instalar con `rest.host` no local emite el aviso de ausencia de autenticacion.
- `docs/DESPLIEGUE.md` no describe pasos que el script ya hace.
- Sin dependencias nuevas. Todo en ASCII.

## Archivos previstos

- `deploy/setup.sh`, `install.sh`
- `deploy/ejemplo.setup.yaml` (plantilla, sin datos reales)
- `docs/DESPLIEGUE.md`, `docs/manual/instalacion.md`
- `CHANGELOG.md`

## No cubre

- Bastionado del entorno, firewall, VLANs o backups: es infraestructura del
  operador y no del ente.
- Autenticacion de las interfaces: concern registrado en
  `ia_nest_meta/docs/CAPAS_FUTURAS.md`, y no se resuelve con una bandera de
  instalador.
- Instalar drivers NVIDIA, Docker o el toolkit de contenedores: el script sigue
  exigiendolos, no los pone.
- La capa de enriquecimiento: su instalacion es de su repo.

## Resultado

Pendiente.
