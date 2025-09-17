#

# TODO: temporary measure so as not to have to overhaul the InstrumentType class logic in one go
#! And also to avoid breaking other parts of the codebase which rely on InstrumentType when for now just working on fetch
# TODO: ideally this can evaporate...
# TODO: discuss to see if there's a better option...!

from enum import Enum

# and so on ...
# from virtualship.instruments.ctd import CTDInputDataset, CTDInstrument


class InstrumentType(Enum):
    """Types of the instruments."""

    CTD = "CTD"
    # CTD_BGC = "CTD_BGC"
    # DRIFTER = "DRIFTER"
    # ARGO_FLOAT = "ARGO_FLOAT"
    # XBT = "XBT"

    # # TODO: should underway also be handled here?!
    # ADCP = "ADCP"
    # UNDERWAY_ST = "UNDERWAY_ST"


# replace with imports instead...
class CTDInputDataset:
    """Input dataset class for CTD instrument."""

    pass


class CTDInstrument:
    """Instrument class for CTD instrument."""

    pass


INSTRUMENTS = {
    inst: {
        "input_class": globals()[f"{inst.value}InputDataset"],
        "instrument_class": globals()[f"{inst.value}Instrument"],
    }
    for inst in InstrumentType
    if f"{inst.value}InputDataset" in globals()
    and f"{inst.value}Instrument" in globals()
}


# INSTRUMENTS = {
#     InstrumentType.CTD: {
#         "input_class": CTDInputDataset,
#         "instrument_class": CTDInstrument,
#     }
#     # and so on for other instruments...
# }

# INSTRUMENTS = {
#     "InstrumentType.CTD": {
#         "input_class": "test",
#         "instrument_class": "test",
#     }
#     # and so on for other instruments...
# }
