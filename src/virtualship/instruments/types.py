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
