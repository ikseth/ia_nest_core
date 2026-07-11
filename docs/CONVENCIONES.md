# Convenciones

## Codigo

- Filosofia UNIX: funciones y scripts pequenos.
- Nombres explicitos y consistentes.
- Identificadores de codigo y claves de configuracion en ingles snake_case;
  la prosa de docs sigue en espanol sin tildes (ADR 0016).
- Sin abreviaturas ambiguas.
- Sin logica implicita si puede declararse en configuracion.
- Sin dependencias globales ocultas.

## Scripts

Todo script no trivial debe incluir cabecera:

- proposito,
- entradas,
- salidas,
- efectos,
- requisitos,
- seguridad.

## Documentacion

- Documentos cortos.
- Una decision por ADR.
- Separar alcance, arquitectura, plan y estado.
- No mezclar ideas futuras con trabajo aprobado.

## IA

- Usar steelman en analisis importantes.
- Preguntar antes de inferir decisiones criticas.
- No ampliar alcance por conveniencia.
- Preferir cambios pequenos y verificables.

