from __future__ import annotations

from dataclasses import dataclass
from datetime import timedelta

from virtualship.instruments.types import InstrumentType

# =====================================================
# SECTION: Problem Classes
# =====================================================


@dataclass
class GeneralProblem:
    """Base class for general problems. Can occur pre-depature or during expedition."""

    short_name: str
    message: str
    delay_duration: timedelta
    pre_departure: bool  # True if problem occurs before expedition departure, False if during expedition

    # TODO: could add a (abstract) method to check if problem is valid for given waypoint, e.g. location (tropical waters etc.)


@dataclass
class InstrumentProblem:
    """Base class for instrument-specific problems. Cannot occur before expedition departure."""

    short_name: str
    message: str
    delay_duration: timedelta
    instrument_type: InstrumentType

    # TODO: could add a (abstract) method to check if problem is valid for given waypoint, e.g. location ()


# =====================================================
# SECTION: General Problems
# =====================================================

GENERAL_PROBLEMS = [
    GeneralProblem(  # Problem: Scheduled food delivery is delayed.
        short_name="scheduled_food_delivery_delayed",
        message=(
            "The scheduled food delivery prior to departure has not arrived. Until the supply truck reaches the pier, "
            "we cannot leave. Once it arrives, unloading and stowing the provisions in the ship's cold storage "
            "will also take additional time. These combined delays postpone departure by 5 hours."
        ),
        delay_duration=timedelta(hours=5.0),
        pre_departure=True,
    ),
    GeneralProblem(  # Problem: Sudden initiation of a mandatory safety drill.
        short_name="safety_drill_initiated",
        message=(
            "A miscommunication with the ship's captain results in the sudden initiation of a mandatory safety drill. "
            "The emergency vessel must be lowered and tested while the ship remains stationary, pausing all scientific "
            "operations for the duration of the exercise. The drill introduces a delay of 2 hours."
        ),
        delay_duration=timedelta(hours=2.0),
        pre_departure=False,
    ),
    GeneralProblem(  # Problem: Fuel delivery tanker delayed.
        short_name="fuel_delivery_tanker_delayed",
        message=(
            "The fuel tanker expected to deliver fuel has not arrived. Until the tanker reaches the pier, "
            "we cannot leave. Once it arrives, securing the fuel lines in the ship's tanks and fueling operations "
            "will also take additional time. These combined delays postpone departure by 5 hours."
        ),
        delay_duration=timedelta(hours=5.0),
        pre_departure=True,
    ),
    GeneralProblem(  # Problem: Marine mammals observed in deployment area.
        short_name="marine_mammals_observed",
        message=(
            "A pod of dolphins is observed swimming directly beneath the planned deployment area. "
            "To avoid risk to wildlife and comply with environmental protocols, all operations "
            "must pause until the animals move away from the vicinity. This results in a delay of about 2 hours."
        ),
        delay_duration=timedelta(hours=2),
        pre_departure=False,
    ),
    GeneralProblem(  # Problem: Ballast pump failure during ballasting operations.
        short_name="ballast_pump_failure",
        message=(
            "One of the ship's ballast pumps suddenly stops responding during routine ballasting operations. "
            "Without the pump, the vessel cannot safely adjust trim or compensate for equipment movements on deck. "
            "Engineering isolates the faulty pump and performs a rapid inspection. Temporary repairs allow limited "
            "functionality, but the interruption causes a delay of 4 hours."
        ),
        delay_duration=timedelta(hours=4.0),
        pre_departure=False,
    ),
    GeneralProblem(  # Problem: Bow thruster's power converter fault during station-keeping.
        short_name="bow_thruster_power_converter_fault",
        message=(
            "The bow thruster's power converter reports a fault during station-keeping operations. "
            "Dynamic positioning becomes less stable, forcing a temporary suspension of high-precision sampling. "
            "Engineers troubleshoot the converter and perform a reset, resulting in a delay of 4 hours."
        ),
        delay_duration=timedelta(hours=4.0),
        pre_departure=False,
    ),
    GeneralProblem(  # Problem: Hydraulic fluid leak from A-frame actuator.
        short_name="hydraulic_fluid_leak_aframe_actuator",
        message=(
            "A crew member notices hydraulic fluid leaking from the A-frame actuator during equipment checks. "
            "The leak must be isolated immediately to prevent environmental contamination or mechanical failure. "
            "Engineering replaces a faulty hose and repressurizes the system. This repair causes a delay of about 6 hours."
        ),
        delay_duration=timedelta(hours=6.0),
        pre_departure=False,
    ),
    GeneralProblem(  # Problem: Main engine's cooling water intake blocked.
        short_name="engine_cooling_intake_blocked",
        message=(
            "The main engine's cooling water intake alarms indicate reduced flow, likely caused by marine debris "
            "or biological fouling. The vessel must temporarily slow down while engineering clears the obstruction "
            "and flushes the intake. This results in a delay of 4 hours."
        ),
        delay_duration=timedelta(hours=4.0),
        pre_departure=False,
    ),
]

# TODO: draft problem below, but needs a method to adjust ETA based on reduced speed (future PR)
# GeneralProblem(
#     short_name="engine_overheat_speed_reduction",
#     message=(
#         "One of the main engines has overheated. To prevent further damage, the engineering team orders a reduction "
#         "in vessel speed until the engine can be inspected and repaired in port. The ship will now operate at a "
#         "reduced cruising speed of 8.5 knots for the remainder of the transit."
#     )
#     delay_duration: None = None  # speed reduction affects ETA instead of fixed delay
#     ship_speed_knots: float = 8.5
# )


# TODO: draft problem below, but needs a method to check if waypoint is in tropical waters (future PR)
# GeneralProblem(
#     short_name="venomous_centipede_onboard",
#     message=(
#         "A venomous centipede is discovered onboard while operating in tropical waters. "
#         "One crew member becomes ill after contact with the creature and receives medical attention, "
#         "prompting a full search of the vessel to ensure no further danger. "
#         "The medical response and search efforts cause an operational delay of about 2 hours."
#     )
#     delay_duration: timedelta = timedelta(hours=2.0)
#     pre_departure: bool = False
# )


# =====================================================
# SECTION: Instrument-specific Problems
# =====================================================

INSTRUMENT_PROBLEMS = [
    InstrumentProblem(  # Problem: CTD cable jammed in winch drum.
        short_name="ctd_cable_jammed",
        message=(
            "During preparation for the next CTD cast, the CTD cable becomes jammed in the winch drum. "
            "Attempts to free it are unsuccessful, and the crew determines that the entire cable must be "
            "replaced before deployment can continue. This repair is time-consuming and results in a delay "
            "of 5 hours."
        ),
        delay_duration=timedelta(hours=5.0),
        instrument_type=InstrumentType.CTD,
    ),
    InstrumentProblem(  # Problem: ADCP returns invalid data.
        short_name="adcp_invalid_data",
        message=(
            "The hull-mounted ADCP begins returning invalid velocity data. Engineering suspects damage to the cable "
            "from recent maintenance activities. The ship must hold position while a technician enters the cable "
            "compartment to perform an inspection and continuity test. This diagnostic procedure results in a delay "
            "of 2 hours."
        ),
        delay_duration=timedelta(hours=2.0),
        instrument_type=InstrumentType.ADCP,
    ),
    InstrumentProblem(  # Problem: CTD temperature sensor failure.
        short_name="ctd_temperature_sensor_failure",
        message=(
            "The primary temperature sensor on the CTD begins returning inconsistent readings. "
            "Troubleshooting confirms that the sensor has malfunctioned. A spare unit can be installed, "
            "but integrating and verifying the replacement will pause operations. "
            "This procedure leads to an estimated delay of 3 hours."
        ),
        delay_duration=timedelta(hours=3.0),
        instrument_type=InstrumentType.CTD,
    ),
    InstrumentProblem(  # Problem: CTD salinity sensor failure.
        short_name="ctd_salinity_sensor_failure",
        message=(
            "The CTD's primary salinity sensor fails and must be replaced with a backup. After installation, "
            "a mandatory calibration cast to a minimum depth of 1000 meters is required to verify sensor accuracy. "
            "Both the replacement and calibration activities result in a total delay of roughly 4 hours."
        ),
        delay_duration=timedelta(hours=4.0),
        instrument_type=InstrumentType.CTD,
    ),
    InstrumentProblem(  # Problem: CTD winch hydraulic pressure drop.
        short_name="ctd_winch_hydraulic_pressure_drop",
        message=(
            "The CTD winch begins to lose hydraulic pressure during routine checks prior to deployment. "
            "The engineering crew must stop operations to diagnose the hydraulic pump and replenish or repair "
            "the system. Until pressure is restored to operational levels, the winch cannot safely be used. "
            "This results in an estimated delay of 2.5 hours."
        ),
        delay_duration=timedelta(hours=2.5),
        instrument_type=InstrumentType.CTD,
    ),
    InstrumentProblem(  # Problem: CTD rosette trigger failure.
        short_name="ctd_rosette_trigger_failure",
        message=(
            "During a CTD cast, the rosette's bottle-triggering mechanism fails to actuate. "
            "No discrete water samples can be collected during this cast. The rosette must be brought back "
            "on deck for inspection and manual testing of the trigger system. This results in an operational "
            "delay of 3.5 hours."
        ),
        delay_duration=timedelta(hours=3.5),
        instrument_type=InstrumentType.CTD,
    ),
    InstrumentProblem(  # Problem: Drifter fails to establish satellite connection before deployment.
        short_name="drifter_satellite_connection_failure",
        message=(
            "The drifter scheduled for deployment fails to establish a satellite connection during "
            "pre-launch checks. To improve signal acquisition, the float must be moved to a higher location on deck "
            "with fewer obstructions. The team waits for the satellite connection to be established, resulting in a delay "
            "of 2 hours."
        ),
        delay_duration=timedelta(hours=2.0),
        instrument_type=InstrumentType.DRIFTER,
    ),
    InstrumentProblem(  # Problem: Argo float fails to establish satellite connection before deployment.
        short_name="argo_float_satellite_connection_failure",
        message=(
            "The Argo float scheduled for deployment fails to establish a satellite connection during "
            "pre-launch checks. To improve signal acquisition, the float must be moved to a higher location on deck "
            "with fewer obstructions. The team waits for the satellite connection to be established, resulting in a delay "
            "of 2 hours."
        ),
        delay_duration=timedelta(hours=2.0),
        instrument_type=InstrumentType.ARGO_FLOAT,
    ),
]
