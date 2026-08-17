"""Gate de la convencion ASCII del repo.

Los documentos y el codigo van sin acentos ni tildes: es convencion deliberada
del proyecto (`ia_nest_meta/docs/CONVENCIONES_TRANSVERSALES.md`, regla 1), no una
errata. Hasta ahora dependia de que alguien mirase, y se colaron dos enes con
virgulilla en dos dias. Esto la hace falsable.

Los DIAGRAMAS si pueden usar caracteres de dibujo de cajas (bloque Unicode
U+2500..U+257F): la convencion persigue los acentos, no las cajas de
`ARCHITECTURE.md`.
"""

from __future__ import annotations

from pathlib import Path

import pytest


REPO = Path(__file__).resolve().parents[1]

SUFFIXES = {".md", ".py", ".yaml", ".yml", ".sh", ".toml", ".example"}
EXCLUDED_DIRS = {".git", ".venv", "local", "build", "dist", "__pycache__", ".pytest_cache"}

# Dibujo de cajas: permitido en diagramas.
BOX_DRAWING = range(0x2500, 0x2580)


def _tracked_text_files() -> list[Path]:
    files: list[Path] = []
    for path in REPO.rglob("*"):
        if not path.is_file():
            continue
        if any(part in EXCLUDED_DIRS for part in path.relative_to(REPO).parts):
            continue
        if path.suffix in SUFFIXES or path.name in {".env.example", "AGENTS.md"}:
            files.append(path)
    return files


def _label(path: Path) -> str:
    try:
        return str(path.relative_to(REPO))
    except ValueError:
        return str(path)


def _offending_lines(path: Path) -> list[str]:
    offences: list[str] = []
    for number, line in enumerate(path.read_text(encoding="utf-8").splitlines(), start=1):
        for character in line:
            if ord(character) < 128 or ord(character) in BOX_DRAWING:
                continue
            offences.append(f"{_label(path)}:{number}: {character!r} en {line.strip()[:60]!r}")
    return offences


def test_repo_files_are_ascii_except_box_drawing() -> None:
    files = _tracked_text_files()
    assert files, "el escaner no encontro ficheros; revisa SUFFIXES y EXCLUDED_DIRS"

    offences = [offence for path in files for offence in _offending_lines(path)]

    assert not offences, (
        "convencion ASCII incumplida (sin acentos ni tildes; ver "
        "ia_nest_meta/docs/CONVENCIONES_TRANSVERSALES.md, regla 1):\n"
        + "\n".join(offences)
    )


def test_gate_detects_an_accent(tmp_path: Path) -> None:
    """El gate tiene que fallar con una tilde; si no, no esta vigilando nada."""
    intruso = tmp_path / "con_acento.md"
    # La tilde se construye por escape para que ESTE fichero siga siendo ASCII:
    # un gate cuyo propio test lo incumple no se sostiene.
    intruso.write_text("una linea con acentuacion: dise\u00f1o\n", encoding="utf-8")

    assert _offending_lines(intruso)


def test_gate_allows_box_drawing(tmp_path: Path) -> None:
    diagrama = tmp_path / "diagrama.md"
    diagrama.write_text("  CLI ─┐\n  REST ─┼─> nucleo\n", encoding="utf-8")

    assert not _offending_lines(diagrama)


@pytest.mark.parametrize("documento", ["docs/ARCHITECTURE.md", "CHANGELOG.md", "AGENTS.md"])
def test_documentos_de_referencia_pasan_el_gate(documento: str) -> None:
    assert not _offending_lines(REPO / documento)
