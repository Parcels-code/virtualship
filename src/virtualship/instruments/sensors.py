from __future__ import annotations

from enum import Enum


class SensorType(str, Enum):
    """Sensors available. Different intstruments mix and match these sensors as needed."""

    TEMPERATURE = "TEMPERATURE"
    SALINITY = "SALINITY"
    VELOCITY = "VELOCITY"
    OXYGEN = "OXYGEN"
    CHLOROPHYLL = "CHLOROPHYLL"
    NITRATE = "NITRATE"
    PHOSPHATE = "PHOSPHATE"
    PH = "PH"
    PHYTOPLANKTON = "PHYTOPLANKTON"
    PRIMARY_PRODUCTION = "PRIMARY_PRODUCTION"
