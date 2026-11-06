# 0014: el instalador no reinicia los servicios al actualizar y su verificacion no lo detecta

Estado: implementada (2026-11-06), verificada en laboratorio (2026-11-06)
Tipo: correccion del instalador
Impacto de version: patch
Version objetivo: v0.4.3

Origen: issue #47, medido en el laboratorio el 2026-10-27 (de `v0.4.0` a
`v0.4.1`) y otra vez el 2026-11-06 (el proceso servia desde el 2026-10-29).
Bloquea en meta el criterio 12 de `H08` (ningun paso a mano) y el tramo 2 de
`H09` (meta H08P12).

## Problema

Una segunda pasada de `deploy/setup.sh` con el mismo `setup.conf` y el arbol en
un tag nuevo termina en verde, pero las units siguen sirviendo el proceso
anterior. `enable_services` usa `systemctl enable --now`, que no reinicia un
servicio activo, y tanto la comprobacion de `/runtime/health` como la
inferencia de `verify_core` las pasa el proceso viejo. La maquina queda con la
version nueva en disco y la vieja en memoria, y el siguiente reinicio cambia la
version sin que nadie lo decida.

## Cambio

1. **Reiniciar siempre que el instalador gestiona los servicios.** Con
   `SERVICE_ENABLE=true`, `enable_services` habilita las dos units y las
   reinicia (`systemctl enable` y despues `systemctl restart`). En una primera
   instalacion, reiniciar un servicio parado lo arranca: no hay dos caminos.
   Es la practica habitual de los instaladores que gestionan su servicio
   (actualizar es reiniciar).
2. **Verificar que responde el arbol instalado.** Tras el puerto y el estado,
   `enable_services` compara el `build_id` que publica `/runtime/health`
   (ADR 0052, D1) con el que calcula el Python del venv instalado sobre el
   paquete instalado. Si no coinciden, o si alguno de los dos es `unknown`,
   es error (el instalador termina con fallo), independiente de `VERIFY`: es
   una comprobacion de la instalacion, no de la inferencia.
3. **La MCP tambien.** La MCP no publica `build_id` por HTTP; basta comprobar
   que su unit se reinicio en esta pasada: su `ActiveEnterTimestampMonotonic`
   es posterior a un instante tomado justo antes del reinicio. Lo mismo se
   comprueba en la REST.

Sin cambios de contrato publico: es el instalador.

## Criterio de aceptacion (falsable)

- En el laboratorio, con el core servido en `v0.4.2`, una segunda pasada del
  instalador con el arbol en esta rama deja `runtime.health` con el
  `core_version` y el `build_id` del arbol instalado, sin ningun paso a mano, y
  el PID de las dos units cambia.
- Si el proceso que responde no es el del arbol instalado (por ejemplo, una
  unit que no se reinicia), el instalador falla con un mensaje que lo dice.
- Pruebas del instalador que cubren las dos cosas sin systemd real.

## Verificacion en laboratorio (2026-11-06)

Core servido en `v0.4.2` desde el 2026-11-06 11:27. Arbol del laboratorio a
esta rama y segunda pasada del instalador con el mismo `setup.conf`: EXIT=0,
las dos units reiniciadas por el instalador (PID nuevo, activas desde la
pasada), `build_id` servido igual al calculado por el venv (el cambio no toca
el paquete, solo `deploy/`) y humo de inferencia correcto. Ningun paso a mano.
Los casos de fallo (unit sin reiniciar, `build_id` distinto o `unknown`) se
cubren con las pruebas del instalador, no en el laboratorio.
