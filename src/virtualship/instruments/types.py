from enum import Enum


class InstrumentType(Enum):
    """Types of the instruments."""

    CTD = "CTD"
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
    """Sensors available (to instruments with configurable sensors, e.g. CTDs). #TODO: and soon Argo floats, drifters."""

    TEMPERATURE = "TEMPERATURE"
    SALINITY = "SALINITY"
    OXYGEN = "OXYGEN"
    CHLOROPHYLL = "CHLOROPHYLL"
    NITRATE = "NITRATE"
    PHOSPHATE = "PHOSPHATE"
    PH = "PH"
    PHYTOPLANKTON = "PHYTOPLANKTON"
    PRIMARY_PRODUCTION = "PRIMARY_PRODUCTION"
