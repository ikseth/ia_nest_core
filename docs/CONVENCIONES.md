# Convenciones

## Codigo

- Filosofia UNIX: funciones y scripts pequenos.
- Nombres explicitos y consistentes.
- Idioma de identificadores, de claves y de la prosa de docs: regla TRANSVERSAL
  del ente, vive en `ia_nest_meta/docs/CONVENCIONES_TRANSVERSALES.md`
  (ingles snake_case para identificadores; docs en ASCII puro). Origen
  historico: ADR 0016.
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
- Las correcciones y mejoras pequenas usan una ficha breve en `docs/fixes/`;
  las decisiones estructurales usan ADR.
- Separar alcance, arquitectura, plan y estado.
- No mezclar ideas futuras con trabajo aprobado.

## IA

- Usar steelman en analisis importantes.
- Preguntar antes de inferir decisiones criticas.
- No ampliar alcance por conveniencia.
- Preferir cambios pequenos y verificables.
