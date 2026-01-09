"""This can be where we house both general and instrument-specific problems."""  # noqa: D404

from __future__ import annotations

import abc
from dataclasses import dataclass
from typing import TYPE_CHECKING

from virtualship.instruments.adcp import ADCP
from virtualship.instruments.argo_float import ArgoFloat
from virtualship.instruments.ctd import CTD
from virtualship.instruments.drifter import Drifter
from virtualship.instruments.types import InstrumentType
from virtualship.utils import register_general_problem, register_instrument_problem

if TYPE_CHECKING:
    from virtualship.models import Waypoint

# @dataclass
# class ProblemConfig:
#     message: str
#     can_reoccur: bool
#     base_probability: float  # Probability is a function of time - the longer the expedition the more likely something is to go wrong (not a function of waypoints)
#     delay_duration: float  # in hours


def general_problem_select() -> bool:
    """Determine if a general problem should occur at a given waypoint."""
    # some random calculation based on the base_probability
    return True


def instrument_problem_select(probability: float, waypoint: Waypoint) -> bool:
    """Determine if an instrument-specific problem should occur at a given waypoint."""
    # set: waypoint instruments vs. list of instrument-specific problems (automated registry)
    # will deterimne which instrument-specific problems are possible at this waypoint

    wp_instruments = waypoint.instruments


# Pseudo-code for problem probability functions
# def instrument_specific_proba(
#     instrument: type,
# ) -> Callable([ProblemConfig, Waypoint], bool):
#     """Return a function to determine if an instrument-specific problem should occur."""

#     def should_occur(config: ProblemConfig, waypoint) -> bool:
#         if instrument not in waypoint.instruments:
#             return False

#         return general_proba_function(config, waypoint)

#     return should_occur

# PROBLEMS: list[Tuple[ProblemConfig, Callable[[ProblemConfig, Waypoint], bool]]] = [
#     (
#         ProblemConfig(
#             message="General problem occurred",
#             can_reoccur=True,
#             base_probability=0.1,
#             delay_duration=2.0,
#         ),
#         general_proba_function,
#     ),
#     (
#         ProblemConfig(
#             message="Instrument-specific problem occurred",
#             can_reoccur=False,
#             base_probability=0.05,
#             delay_duration=4.0,
#         ),
#         instrument_specific_proba(CTD),
#     ),
# ]


##### BASE CLASSES FOR PROBLEMS #####


@dataclass
class GeneralProblem(abc.ABC):
    """
    Base class for general problems.

    Problems occur at each waypoint.
    """

    message: str
    can_reoccur: bool
    base_probability: float  # Probability is a function of time - the longer the expedition the more likely something is to go wrong (not a function of waypoints)
    delay_duration: float  # in hours
    pre_departure: bool  # True if problem occurs before expedition departure, False if during expedition

    @abc.abstractmethod
    def is_valid() -> bool:
        """Check if the problem can occur based on e.g. waypoint location and/or datetime etc."""
        ...


@dataclass
class InstrumentProblem(abc.ABC):
    """Base class for instrument-specific problems."""

    instrument_dataclass: type
    message: str
    can_reoccur: bool
    base_probability: float  # Probability is a function of time - the longer the expedition the more likely something is to go wrong (not a function of waypoints)
    delay_duration: float  # in hours
    pre_departure: bool  # True if problem can occur before expedition departure, False if during expedition

    @abc.abstractmethod
    def is_valid() -> bool:
        """Check if the problem can occur based on e.g. waypoint location and/or datetime etc."""
        ...


##### Specific Problems #####


### General problems


@register_general_problem
class VenomousCentipedeOnboard(GeneralProblem):
    """Problem: Venomous centipede discovered onboard in tropical waters."""

    # TODO: this needs logic added to the is_valid() method to check if waypoint is in tropical waters

    message: str = (
        "A venomous centipede is discovered onboard while operating in tropical waters. "
        "One crew member becomes ill after contact with the creature and receives medical attention, "
        "prompting a full search of the vessel to ensure no further danger. "
        "The medical response and search efforts cause an operational delay of about 2 hours."
    )
    can_reoccur = False
    delay_duration = 2.0
    base_probability = 0.05
    pre_departure = False

    def is_valid(self, waypoint: Waypoint) -> bool:
        """Check if the waypoint is in tropical waters."""
        lat_limit = 23.5  # [degrees]
        return abs(waypoint.latitude) <= lat_limit


@register_general_problem
class CaptainSafetyDrill(GeneralProblem):
    """Problem: Sudden initiation of a mandatory safety drill."""

    message: str = (
        "A miscommunication with the ship’s captain results in the sudden initiation of a mandatory safety drill. "
        "The emergency vessel must be lowered and tested while the ship remains stationary, pausing all scientific "
        "operations for the duration of the exercise. The drill introduces a delay of approximately 2 hours."
    )
    can_reoccur: False
    delay_duration: 2.0
    base_probability = 0.1
    pre_departure = False


# @dataclass
# class FoodDeliveryDelayed:
#     message: str = (
#         "The scheduled food delivery prior to departure has not arrived. Until the supply truck reaches the pier, "
#         "we cannot leave. Once it arrives, unloading and stowing the provisions in the ship’s cold storage "
#         "will also take additional time. These combined delays postpone departure by approximately 5 hours."
#     )
#     can_reoccur: bool = False
#     delay_duration: float = 5.0

# @dataclass
# class FuelDeliveryIssue:
#     message: str = (
#         "The fuel tanker expected to deliver fuel has not arrived. Port authorities are unable to provide "
#         "a clear estimate for when the delivery might occur. You may choose to [w]ait for the tanker or [g]et a "
#         "harbor pilot to guide the vessel to an available bunker dock instead. This decision may need to be "
#         "revisited periodically depending on circumstances."
#     )
#     can_reoccur: bool = False
#     delay_duration: float = 0.0  # dynamic delays based on repeated choices

# @dataclass
# class EngineOverheating:
#     message: str = (
#         "One of the main engines has overheated. To prevent further damage, the engineering team orders a reduction "
#         "in vessel speed until the engine can be inspected and repaired in port. The ship will now operate at a "
#         "reduced cruising speed of 8.5 knots for the remainder of the transit."
#     )
#     can_reoccur: bool = False
#     delay_duration: None = None  # speed reduction affects ETA instead of fixed delay
#     ship_speed_knots: float = 8.5


@register_general_problem
class MarineMammalInDeploymentArea(GeneralProblem):
    """Problem: Marine mammals observed in deployment area, causing delay."""

    message: str = (
        "A pod of dolphins is observed swimming directly beneath the planned deployment area. "
        "To avoid risk to wildlife and comply with environmental protocols, all in-water operations "
        "must pause until the animals move away from the vicinity. This results in a delay of about 30 minutes."
    )
    can_reoccur: bool = True
    delay_duration: float = 0.5
    base_probability: float = 0.1


@register_general_problem
class BallastPumpFailure(GeneralProblem):
    """Problem: Ballast pump failure during ballasting operations."""

    message: str = (
        "One of the ship’s ballast pumps suddenly stops responding during routine ballasting operations. "
        "Without the pump, the vessel cannot safely adjust trim or compensate for equipment movements on deck. "
        "Engineering isolates the faulty pump and performs a rapid inspection. Temporary repairs allow limited "
        "functionality, but the interruption causes a delay of approximately 1 hour."
    )
    can_reoccur: bool = True
    delay_duration: float = 1.0
    base_probability: float = 0.1


@register_general_problem
class ThrusterConverterFault(GeneralProblem):
    """Problem: Bow thruster's power converter fault during station-keeping."""

    message: str = (
        "The bow thruster's power converter reports a fault during station-keeping operations. "
        "Dynamic positioning becomes less stable, forcing a temporary suspension of high-precision sampling. "
        "Engineers troubleshoot the converter and perform a reset, resulting in a delay of around 1 hour."
    )
    can_reoccur: bool = False
    delay_duration: float = 1.0
    base_probability: float = 0.1


@register_general_problem
class AFrameHydraulicLeak(GeneralProblem):
    """Problem: Hydraulic fluid leak from A-frame actuator."""

    message: str = (
        "A crew member notices hydraulic fluid leaking from the A-frame actuator during equipment checks. "
        "The leak must be isolated immediately to prevent environmental contamination or mechanical failure. "
        "Engineering replaces a faulty hose and repressurizes the system. This repair causes a delay of about 2 hours."
    )
    can_reoccur: bool = True
    delay_duration: float = 2.0
    base_probability: float = 0.1


@register_general_problem
class CoolingWaterIntakeBlocked(GeneralProblem):
    """Problem: Main engine's cooling water intake blocked."""

    message: str = (
        "The main engine's cooling water intake alarms indicate reduced flow, likely caused by marine debris "
        "or biological fouling. The vessel must temporarily slow down while engineering clears the obstruction "
        "and flushes the intake. This results in a delay of approximately 1 hour."
    )
    can_reoccur: bool = True
    delay_duration: float = 1.0
    base_probability: float = 0.1


### Instrument-specific problems


@register_instrument_problem(InstrumentType.CTD)
class CTDCableJammed(InstrumentProblem):
    """Problem: CTD cable jammed in winch drum, requiring replacement."""

    message: str = (
        "During preparation for the next CTD cast, the CTD cable becomes jammed in the winch drum. "
        "Attempts to free it are unsuccessful, and the crew determines that the entire cable must be "
        "replaced before deployment can continue. This repair is time-consuming and results in a delay "
        "of approximately 3 hours."
    )
    can_reoccur: bool = True
    delay_duration: float = 3.0
    base_probability: float = 0.1
    instrument_dataclass = CTD


@register_instrument_problem(InstrumentType.CTD)
class CTDTemperatureSensorFailure(InstrumentProblem):
    """Problem: CTD temperature sensor failure, requiring replacement."""

    message: str = (
        "The primary temperature sensor on the CTD begins returning inconsistent readings. "
        "Troubleshooting confirms that the sensor has malfunctioned. A spare unit can be installed, "
        "but integrating and verifying the replacement will pause operations. "
        "This procedure leads to an estimated delay of around 2 hours."
    )
    can_reoccur: bool = True
    delay_duration: float = 2.0
    base_probability: float = 0.1
    instrument_dataclass = CTD


@register_instrument_problem(InstrumentType.CTD)
class CTDSalinitySensorFailureWithCalibration(InstrumentProblem):
    """Problem: CTD salinity sensor failure, requiring replacement and calibration."""

    message: str = (
        "The CTD’s primary salinity sensor fails and must be replaced with a backup. After installation, "
        "a mandatory calibration cast to a minimum depth of 1000 meters is required to verify sensor accuracy. "
        "Both the replacement and calibration activities result in a total delay of roughly 4 hours."
    )
    can_reoccur: bool = True
    delay_duration: float = 4.0
    base_probability: float = 0.1
    instrument_dataclass = CTD


@register_instrument_problem(InstrumentType.CTD)
class WinchHydraulicPressureDrop(InstrumentProblem):
    """Problem: CTD winch hydraulic pressure drop, requiring repair."""

    message: str = (
        "The CTD winch begins to lose hydraulic pressure during routine checks prior to deployment. "
        "The engineering crew must stop operations to diagnose the hydraulic pump and replenish or repair "
        "the system. Until pressure is restored to operational levels, the winch cannot safely be used. "
        "This results in an estimated delay of 1.5 hours."
    )
    can_reoccur: bool = True
    delay_duration: float = 1.5
    base_probability: float = 0.1
    instrument_dataclass = CTD


@register_instrument_problem(InstrumentType.CTD)
class RosetteTriggerFailure(InstrumentProblem):
    """Problem: CTD rosette trigger failure, requiring inspection."""

    message: str = (
        "During a CTD cast, the rosette's bottle-triggering mechanism fails to actuate. "
        "No discrete water samples can be collected during this cast. The rosette must be brought back "
        "on deck for inspection and manual testing of the trigger system. This results in an operational "
        "delay of approximately 2.5 hours."
    )
    can_reoccur: bool = True
    delay_duration: float = 2.5
    base_probability: float = 0.1
    instrument_dataclass = CTD


@register_instrument_problem(InstrumentType.ADCP)
class ADCPMalfunction(InstrumentProblem):
    """Problem: ADCP returns invalid data, requiring inspection."""

    message: str = (
        "The hull-mounted ADCP begins returning invalid velocity data. Engineering suspects damage to the cable "
        "from recent maintenance activities. The ship must hold position while a technician enters the cable "
        "compartment to perform an inspection and continuity test. This diagnostic procedure results in a delay "
        "of around 1 hour."
    )
    can_reoccur: bool = True
    delay_duration: float = 1.0
    base_probability: float = 0.1
    instrument_dataclass = ADCP


@register_instrument_problem(InstrumentType.DRIFTER)
class DrifterSatelliteConnectionDelay(InstrumentProblem):
    """Problem: Drifter fails to establish satellite connection before deployment."""

    message: str = (
        "The drifter scheduled for deployment fails to establish a satellite connection during "
        "pre-launch checks. To improve signal acquisition, the float must be moved to a higher location on deck "
        "with fewer obstructions. The team waits for the satellite fix to come through, resulting in a delay "
        "of approximately 2 hours."
    )
    can_reoccur: bool = True
    delay_duration: float = 2.0
    base_probability: float = 0.1
    instrument_dataclass = Drifter


@register_instrument_problem(InstrumentType.ARGO_FLOAT)
class ArgoSatelliteConnectionDelay(InstrumentProblem):
    """Problem: Argo float fails to establish satellite connection before deployment."""

    message: str = (
        "The Argo float scheduled for deployment fails to establish a satellite connection during "
        "pre-launch checks. To improve signal acquisition, the float must be moved to a higher location on deck "
        "with fewer obstructions. The team waits for the satellite fix to come through, resulting in a delay "
        "of approximately 2 hours."
    )
    can_reoccur: bool = True
    delay_duration: float = 2.0
    base_probability: float = 0.1
    instrument_dataclass = ArgoFloat
