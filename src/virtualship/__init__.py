"""Code for the Virtual Ship Classroom, where Marine Scientists can combine Copernicus Marine Data with an OceanParcels ship to go on a virtual expedition."""

from importlib.metadata import version as _version

try:
    __version__ = _version("virtualship")
except Exception:
    # Local copy or not installed with setuptools
    __version__ = "unknown"

__all__ = [
    "__version__",
]
