"""IA_NEST Core package."""

from importlib.metadata import PackageNotFoundError, version

try:
    __version__ = version("ianest-core")
except PackageNotFoundError:
    __version__ = "0.0.0.dev0"
