from __future__ import annotations

from enum import Enum


class InstrumentType(Enum):
    """Types of the instruments."""

    CTD = "CTD"
    CTD_BGC = "CTD_BGC"
    DRIFTER = "DRIFTER"
    ARGO_FLOAT = "ARGO_FLOAT"
    XBT = "XBT"
    ADCP = "ADCP"
    UNDERWATER_ST = "UNDERWATER_ST"

    @property
    def is_underway(self) -> bool:
        """Return True if instrument is an underway instrument (ADCP, UNDERWATER_ST)."""
        return self in {InstrumentType.ADCP, InstrumentType.UNDERWATER_ST}


class SensorType(str, Enum):
    """
    Sensors available. Different intstruments mix and match these sensors as needed.

    Each entry has a corresponding entry in `SENSOR_REGISTRY` which carries the centralised metadata (e.g. FieldSet key, Copernicus var name).
    """

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


# per-instrument allowlists of supported sensors (source truth for validation for which sensors each instrument supports)

ARGO_FLOAT_SUPPORTED_SENSORS: frozenset[SensorType] = frozenset(
    {SensorType.TEMPERATURE, SensorType.SALINITY}
)

# TODO: CTD and CTD_BGC will be consoidated in future PR...
CTD_SUPPORTED_SENSORS: frozenset[SensorType] = frozenset(
    {SensorType.TEMPERATURE, SensorType.SALINITY}
)

CTD_BGC_SUPPORTED_SENSORS: frozenset[SensorType] = frozenset(
    {
        SensorType.OXYGEN,
        SensorType.CHLOROPHYLL,
        SensorType.NITRATE,
        SensorType.PHOSPHATE,
        SensorType.PH,
        SensorType.PHYTOPLANKTON,
        SensorType.PRIMARY_PRODUCTION,
    }
)

DRIFTER_SUPPORTED_SENSORS: frozenset[SensorType] = frozenset({SensorType.TEMPERATURE})

ADCP_SUPPORTED_SENSORS: frozenset[SensorType] = frozenset({SensorType.VELOCITY})

UNDERWATER_ST_SUPPORTED_SENSORS: frozenset[SensorType] = frozenset(
    {SensorType.TEMPERATURE, SensorType.SALINITY}
)

XBT_SUPPORTED_SENSORS: frozenset[SensorType] = frozenset({SensorType.TEMPERATURE})
