from enum import Enum


class InstrumentType(Enum):
    """Types of the instruments."""

    # TODO: scope for this to evaporate in the future...?

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


def get_instruments_registry():
    # local imports to avoid circular import issues
    from virtualship.instruments.adcp import ADCPInputDataset
    from virtualship.instruments.argo_float import ArgoFloatInputDataset
    from virtualship.instruments.ctd import CTDInputDataset
    from virtualship.instruments.ctd_bgc import CTD_BGCInputDataset
    from virtualship.instruments.drifter import DrifterInputDataset
    from virtualship.instruments.ship_underwater_st import Underwater_STInputDataset
    from virtualship.instruments.xbt import XBTInputDataset

    _input_class_map = {
        "CTD": CTDInputDataset,
        "CTD_BGC": CTD_BGCInputDataset,
        "DRIFTER": DrifterInputDataset,
        "ARGO_FLOAT": ArgoFloatInputDataset,
        "XBT": XBTInputDataset,
        "ADCP": ADCPInputDataset,
        "UNDERWATER_ST": Underwater_STInputDataset,
    }

    return {
        inst: {
            "input_class": _input_class_map.get(inst.value),
        }
        for inst in InstrumentType
        if _input_class_map.get(inst.value) is not None
    }
