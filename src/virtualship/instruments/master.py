from enum import Enum


class InstrumentType(Enum):
    """Types of the instruments."""

    # TODO: temporary measure so as not to have to overhaul the InstrumentType class logic in one go
    #! And also to avoid breaking other parts of the codebase which rely on InstrumentType when for now just working on fetch
    # TODO: ideally this can evaporate in the future...

    CTD = "CTD"
    CTD_BGC = "CTD_BGC"
    DRIFTER = "DRIFTER"
    ARGO_FLOAT = "ARGO_FLOAT"
    XBT = "XBT"
    ADCP = "ADCP"
    UNDERWATER_ST = "UNDERWATER_ST"


def get_instruments_registry():
    # local imports to avoid circular import issues
    from virtualship.instruments.adcp import ADCPInputDataset, ADCPInstrument
    from virtualship.instruments.argo_float import (
        ArgoFloatInputDataset,
        ArgoFloatInstrument,
    )
    from virtualship.instruments.ctd import CTDInputDataset, CTDInstrument
    from virtualship.instruments.ctd_bgc import CTD_BGCInputDataset, CTD_BGCInstrument
    from virtualship.instruments.drifter import DrifterInputDataset, DrifterInstrument
    from virtualship.instruments.ship_underwater_st import (
        Underwater_STInputDataset,
        Underwater_STInstrument,
    )
    from virtualship.instruments.xbt import XBTInputDataset, XBTInstrument

    _input_class_map = {
        "CTD": CTDInputDataset,
        "CTD_BGC": CTD_BGCInputDataset,
        "DRIFTER": DrifterInputDataset,
        "ARGO_FLOAT": ArgoFloatInputDataset,
        "XBT": XBTInputDataset,
        "ADCP": ADCPInputDataset,
        "UNDERWATER_ST": Underwater_STInputDataset,
    }

    _instrument_class_map = {
        "CTD": CTDInstrument,
        "CTD_BGC": CTD_BGCInstrument,
        "DRIFTER": DrifterInstrument,
        "ARGO_FLOAT": ArgoFloatInstrument,
        "XBT": XBTInstrument,
        "ADCP": ADCPInstrument,
        "UNDERWATER_ST": Underwater_STInstrument,
    }

    return {
        inst: {
            "input_class": _input_class_map.get(inst.value),
            "instrument_class": _instrument_class_map.get(inst.value),
        }
        for inst in InstrumentType
        if _input_class_map.get(inst.value) is not None
        and _instrument_class_map.get(inst.value) is not None
    }
