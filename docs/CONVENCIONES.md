# Convenciones

## Comprobacion automatica de la convencion ASCII

`tests/test_convenciones.py` recorre los ficheros de texto del repo -docs,
codigo, config, scripts- y falla si aparece cualquier caracter fuera de ASCII,
con el fichero, la linea y el caracter.

Excepcion declarada: el bloque Unicode de dibujo de cajas (U+2500..U+257F), que
usan los diagramas de `ARCHITECTURE.md`. La convencion persigue acentos y
tildes, no las cajas.

Por que existe: la regla dependia de que alguien mirase, y en dos dias se
colaron dos enes con virgulilla en documentos recien escritos. Una convencion
que solo vive en la cabeza de quien revisa se incumple en cuanto hay prisa.

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

## Laboratorio

- **Al cerrar una puerta de laboratorio, si hubo que tocar configuracion para
  que pasara, se decide EXPLICITAMENTE que clase de cambio fue**:

      contexto de la maquina   -> se queda en `local/` para siempre
      (endpoint, direcciones,     No es conocimiento sobre el producto.
       nombres de instancia)

      defecto mejor            -> cambia la plantilla versionada en la MISMA
      (que modelo para que        pasada, con el motivo escrito EN la plantilla
       papel, que limite)         y no solo en el commit.

  Motivo, con caso real: el laboratorio de v0.3 descubrio que el planificador
  debia ser `qwen_tech` y lo dejo en un `core.yaml` de `local/`. La plantilla
  versionada siguio trayendo un modelo de razonamiento como planificador, que no
  cabe en el techo de tokens por defecto, y en v0.4 la orquestacion multi-modelo
  no llegaba a ocurrir NUNCA. El conocimiento existia y no llego a donde se usa.

- Un ajuste que se repite entre lineas de version no es un ajuste: es un defecto
  equivocado.

- El motivo de un defecto no obvio se escribe donde vive el defecto. Quien lea la
  plantilla tiene que entender por que ese valor, o el proximo lo deshace de
  buena fe.

## IA

- Usar steelman en analisis importantes.
- Preguntar antes de inferir decisiones criticas.
- No ampliar alcance por conveniencia.
- Preferir cambios pequenos y verificables.
