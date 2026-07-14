# Decision 0025: system prompt por perfil (directiva de idioma/comportamiento)

Fecha: 2026-07-14

## Decision

Los perfiles (ADR 0014) admiten un campo opcional `system`: un system prompt
que el runtime antepone como mensaje `{role: system}` a la peticion del
modelo, en `prompt.run` y `reasoning.run`. Uso principal inmediato: forzar el
idioma de salida (p.ej. "Responde siempre en espanol.") en dominios donde el
modelo tiende a otro idioma.

## Motivo

Un modelo tecnico (p.ej. qwen) a veces responde en su idioma nativo; una
directiva declarativa por perfil lo corrige sin acoplar logica al codigo
(principio de configuracion declarativa). Un `system` general es mas util y
menos rigido que un campo `language` estrecho.

## Consecuencia

- Esquema de config (ADR 0014): `profiles` admiten `system` opcional (string).
- El runtime antepone `{role: system, content: profile.system}` si esta
  presente; sin cambios de comportamiento si no se define (compatibilidad).

## Alternativa registrada pero descartada para el core

El enfoque propuesto por el usuario -"traducir y verificar la respuesta con un
modelo de control": prompt al modelo destino en su idioma fuerte y luego
traduccion + verificacion por un modelo/dominio de control- es potente, pero
es una capa de conciencia/verificacion. Pertenece a `ia_nest_core_conscience`
(fuera del core, anti-entropia). Se documenta como capacidad futura de esa
capa en la fase 10 (fronteras hacia repos externos).
