"""Conversion functions from zarr instrument results to realistic file formats with data adjusted to be more realistic."""

from .adcp_make_realistic import adcp_make_realistic
from .ctd_make_realistic import ctd_make_realistic

__all__ = ["adcp_make_realistic", "ctd_make_realistic"]
