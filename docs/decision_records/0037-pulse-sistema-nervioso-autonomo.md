# Decision 0037: pulse - sistema nervioso autonomo del ente (reconcilia ops)

Fecha: 2026-07-17

## Decision

El ente IA_NEST distingue dos funciones nerviosas, hermanas y de naturaleza
opuesta:

- **conscience = sistema nervioso VOLUNTARIO** (deliberativo): etica,
  personalidad, juicios con valores. Inferencia (GPU).
- **pulse = sistema nervioso AUTONOMO/involuntario** (homeostatico):
  regulacion tecnica refleja. Muestreo + control (CPU/RAM, sin GPU/VRAM).

`pulse` renombra y reconcilia la capa antes llamada `ia_nest_core_ops`. Es el
motor de monitorizacion headless del ente: muestrea a frecuencia fija, decide y
actua.

- **Observa:** consume la telemetria de TODOS los componentes (core, extended,
  y la propia conscience).
- **Regula:** ajusta parametros tecnicos DENTRO de los techos de seguridad del
  core (p.ej. presupuesto de tokens por dominio segun el historico de
  truncados). El core da el arco reflejo (senal + perilla + techo); pulse da la
  POLITICA. El core nunca adivina el limite ideal.
- **Subordinado a conscience:** lo voluntario puede vetar lo involuntario
  (aguantar la respiracion).
- **Fuera de banda:** los ajustes son un evento aparte y registrado; NO ocurren
  dentro de `task.run`, que sigue siendo determinista (se preserva el digest de
  conformance).

Sub-modos (analogia nerviosa): homeostasis continua (parasimpatico: tuning
rutinario) y respuesta a disparadores/incidentes (simpatico: futuro).

## Fronteras

- **vs GUI (`ia_nest_web`):** la GUI es PRESENTACION (visualiza estado,
  telemetria, gestion para el humano); pulse es el MOTOR headless. La GUI lee el
  estado y las senales de pulse; pulse no dibuja nada. (El "aferente" que se
  hace visible al humano es la GUI; el "eferente" que actua es pulse.)
- **vs conscience:** pulse es mecanico/reflejo/continuo; conscience es
  valorativo/deliberativo. La linea es voluntario/involuntario.
- **vs core:** pulse consume contratos publicos y telemetria; no vive dentro del
  motor.

## Motivo

Se identifico una funcion critica -autorregulacion tecnica involuntaria- sin
hogar. Meterla en el orquestador rompia el determinismo de `task.run`; meterla
en conscience rompia su pureza psicologica. Dos criterios independientes cortan
por la misma junta: funcion (voluntario/involuntario) y sustrato (GPU que
piensa / CPU que regula). Cuando ambos coinciden, la junta es real. `pulse`
(latido, pulso sanguineo) nombra ese ritmo involuntario, en el registro de
`conscience`.

## Consecuencia

- Supersede el encuadre de ops como capa EXTERIOR que solo "observa y alerta"
  (ADR 0033/0034): `ops -> pulse`, pasa al interior del ente (pack basico) y su
  alcance crece a observar + regular.
- Pack basico del ente: core + extended + conscience + pulse + GUI.
- Prerrequisito foundational: el core debe exponer `finish_reason` (truncado vs
  parada natural) por llamada/subtarea; sin esa senal, pulse no puede regular.
  Se implementara como cambio pequeno de core (ficha), no dentro de esta ADR.
- Primera responsabilidad concreta de pulse (futura, no se construye sin la
  senal ni sin uso -leccion MemoryPort-): presupuesto dinamico de tokens por
  dominio a partir del historico de truncados.
- Mapa (`IA_NEST_CORE_CONTEXT.md`), registro de capas (`docs/FRONTERAS.md`) y
  `docs/CAPAS_FUTURAS.md` actualizados.
