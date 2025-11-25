"""This can be where we house both genreal and instrument-specific probelems."""  # noqa: D404

from dataclasses import dataclass

import pydantic

from virtualship.instruments.ctd import CTD

# base classes


class GeneralProblem(pydantic.BaseModel):
    """Base class for general problems."""

    message: str
    can_reoccur: bool
    delay_duration: float  # in hours


class InstrumentProblem(pydantic.BaseModel):
    """Base class for instrument-specific problems."""

    instrument_dataclass: type
    message: str
    can_reoccur: bool
    delay_duration: float  # in hours


# Genreral problems


@dataclass
class EngineProblem_FuelLeak(GeneralProblem): ...  # noqa: D101


@dataclass
class FoodDelivery_Delayed(GeneralProblem): ...  # noqa: D101


# Instrument-specific problems


@dataclass
class CTDPRoblem_Winch_Failure(InstrumentProblem):  # noqa: D101
    instrument_dataclass = CTD
    message: str = ...
    can_reoccur: bool = ...
    delay_duration: float = ...  # in hours
