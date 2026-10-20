from __future__ import annotations

import hashlib
from pathlib import Path

import ianest_core


def build_id() -> str:
    """Return the identity of the imported package artifact."""
    return _BUILD_ID


def _calculate_build_id() -> str:
    """Calculate the imported package artifact identity, or ``unknown``."""
    try:
        package_file = ianest_core.__file__
        if package_file is None:
            return "unknown"
        package_root = Path(package_file).resolve().parent
        paths = sorted(
            (
                path
                for path in package_root.rglob("*.py")
                if "__pycache__" not in path.relative_to(package_root).parts
            ),
            key=lambda path: path.relative_to(package_root).as_posix(),
        )
        digest = hashlib.sha256()
        for path in paths:
            relative = path.relative_to(package_root).as_posix().encode("utf-8")
            digest.update(relative)
            digest.update(b"\0")
            digest.update(path.read_bytes())
            digest.update(b"\0")
        return digest.hexdigest()
    except Exception:
        return "unknown"


_BUILD_ID = _calculate_build_id()
