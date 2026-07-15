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
