# Decision 0032: dependencias entre capas (contrato de vinculo)

Fecha: 2026-07-15

## Decision

Las capas del ecosistema (cada una en su repo) pueden depender del core y unas
de otras. Ese vinculo se gobierna con la misma disciplina que el core (ADR 0030,
`docs/VERSIONADO.md`):

- Cada capa versiona su PROPIO contrato publico con SemVer.
- Una capa que depende de otra (o del core) FIJA la version de la que depende
  (rango SemVer), y lo declara de forma explicita en su repo (manifiesto
  "depende-de": core + otras capas, con sus versiones).
- El contrato consumido vive en la capa "de arriba" (la que se consume), no en
  el core. El core NO absorbe logica entre-capas.
- El core hospeda solo el INDICE/grafo: el registro de capas de
  `docs/FRONTERAS.md` anota quien depende de quien y por que costura, para que el
  ecosistema sea descubrible sin hacer crecer el core.

## Motivo

Es previsible que unas capas necesiten a otras (p.ej. control/verificacion
necesita memoria; la GUI web necesita el core y quiza enriquecimiento). Sin un
contrato de vinculo, esas dependencias derivan en acoplamiento implicito y
roturas silenciosas. Reusar SemVer (ADR 0030) da una regla ya conocida por los
tres participantes (usuario, Codex, Claude Code) y por las capas externas.

## Consecuencia

- `docs/FRONTERAS.md` incorpora un "Registro de capas" (indice + grafo de
  dependencias por costura y estado).
- Cada repo de capa incluye su manifiesto de dependencias (formato concreto se
  fija al sembrar la primera capa).
- En modo ciego multi-IA, si dos capas cambian contrato en paralelo, la
  reconciliacion del usuario decide las versiones; ningun agente corta tags de
  una capa por su cuenta.

## Estado posterior

Re-hogado el indice (2026-07-26). La REGLA de vinculo de esta decision sigue
vigente sin cambios: cada capa versiona su contrato, fija por SemVer la version
de la que depende y lo declara en un manifiesto propio.

Lo que queda superado es una sola frase de la seccion Decision: "el core hospeda
solo el INDICE/grafo". El registro de capas y su grafo viven hoy en
`ia_nest_meta/docs/REGISTRO_CAPAS.md` (meta ADR 0003), porque la tabla tiene
zonas "Ente" y "Exterior" y el propio repo de gobernanza no cabe en ninguna de
las dos. El core conserva en `docs/FRONTERAS.md` lo que si es suyo: que costura
expone a cada capa.

Este ADR se conserva sin cambios en su cuerpo, como registro de cuando y por que
se decidio.
