"""do_expedition function."""

import logging
import os
import shutil
from pathlib import Path

import pyproj

from virtualship.cli._fetch import get_existing_download, get_space_time_region_hash
from virtualship.models import Schedule
from virtualship.utils import (
    CHECKPOINT,
    _get_expedition,
    get_instrument_class,
)

from .checkpoint import Checkpoint
from .expedition_cost import expedition_cost
from .simulate_schedule import (
    MeasurementsToSimulate,
    ScheduleProblem,
    simulate_schedule,
)

# projection used to sail between waypoints
projection = pyproj.Geod(ellps="WGS84")


# parcels logger (suppress INFO messages to prevent log being flooded)
external_logger = logging.getLogger("parcels.tools.loggers")
external_logger.setLevel(logging.WARNING)

# copernicusmarine logger (suppress INFO messages to prevent log being flooded)
logging.getLogger("copernicusmarine").setLevel("ERROR")


def do_expedition(expedition_dir: str | Path, from_copernicusmarine: bool) -> None:
    """
    Perform an expedition, providing terminal feedback and file output.

    :param expedition_dir: The base directory for the expedition.
    :param from_copernicusmarine: Whether to use direct data ingestion from Copernicus Marine. Should be determined by CLI flag.
    """
    # ################################# TEMPORARY TIMER: START #################################
    import time

    start_time = time.time()
    print("[TIMER] Expedition started...")
    # ################################# TEMPORARY TIMER: START #################################

    print("\n╔═════════════════════════════════════════════════╗")
    print("║          VIRTUALSHIP EXPEDITION STATUS          ║")
    print("╚═════════════════════════════════════════════════╝")

    if isinstance(expedition_dir, str):
        expedition_dir = Path(expedition_dir)

    expedition = _get_expedition(expedition_dir)

    # Verify instruments_config file is consistent with schedule
    expedition.instruments_config.verify(expedition)

    # load last checkpoint
    checkpoint = _load_checkpoint(expedition_dir)
    if checkpoint is None:
        checkpoint = Checkpoint(past_schedule=Schedule(waypoints=[]))

    # verify that schedule and checkpoint match
    checkpoint.verify(expedition.schedule)

    print("\n---- WAYPOINT VERIFICATION ----")

    # verify schedule is valid
    if from_copernicusmarine:
        bathy_data_dir = None
    else:
        bathy_data_dir = get_existing_download(
            expedition_dir,
            get_space_time_region_hash(expedition.schedule.space_time_region),
        )

    expedition.schedule.verify(expedition.ship_config.ship_speed_knots, bathy_data_dir)

    # simulate the schedule
    schedule_results = simulate_schedule(
        projection=projection,
        expedition=expedition,
    )
    if isinstance(schedule_results, ScheduleProblem):
        print(
            "Update your schedule and continue the expedition by running the tool again."
        )
        _save_checkpoint(
            Checkpoint(
                past_schedule=Schedule(
                    waypoints=expedition.schedule.waypoints[
                        : schedule_results.failed_waypoint_i
                    ]
                )
            ),
            expedition_dir,
        )
        return

    # delete and create results directory
    if os.path.exists(expedition_dir.joinpath("results")):
        shutil.rmtree(expedition_dir.joinpath("results"))
    os.makedirs(expedition_dir.joinpath("results"))

    print("\n----- EXPEDITION SUMMARY ------")

    # expedition cost in US$
    _write_expedition_cost(expedition, schedule_results, expedition_dir)

    print("\n--- MEASUREMENT SIMULATIONS ---")

    # simulate measurements
    print("\nSimulating measurements. This may take a while...\n")

    instruments_in_expedition = expedition.get_instruments()

    for itype in instruments_in_expedition:
        # get instrument class
        instrument_class = get_instrument_class(itype)
        if instrument_class is None:
            raise RuntimeError(f"No instrument class found for type {itype}.")

        # get measurements to simulate
        attr = MeasurementsToSimulate.get_attr_for_instrumenttype(itype)
        measurements = getattr(schedule_results.measurements_to_simulate, attr)

        # initialise instrument
        instrument = instrument_class(
            expedition=expedition,
            directory=expedition_dir,
            from_copernicusmarine=from_copernicusmarine,
        )

        # run simulation
        instrument.run(
            measurements=measurements,
            out_path=expedition_dir.joinpath("results", f"{itype.name.lower()}.zarr"),
        )

    print("\nAll measurement simulations are complete.")

    print("\n----- EXPEDITION RESULTS ------")
    print("\nYour expedition has concluded successfully!")
    print(
        f"Your measurements can be found in the '{expedition_dir}/results' directory."
    )
    print("\n------------- END -------------\n")

    ################################# TEMPORARY TIMER: END #################################
    end_time = time.time()
    elapsed = end_time - start_time
    print(f"[TIMER] Expedition completed in {elapsed:.2f} seconds.")
    ################################# TEMPORARY TIMER: END #################################


def _load_checkpoint(expedition_dir: Path) -> Checkpoint | None:
    file_path = expedition_dir.joinpath(CHECKPOINT)
    try:
        return Checkpoint.from_yaml(file_path)
    except FileNotFoundError:
        return None


def _save_checkpoint(checkpoint: Checkpoint, expedition_dir: Path) -> None:
    file_path = expedition_dir.joinpath(CHECKPOINT)
    checkpoint.to_yaml(file_path)


def _write_expedition_cost(expedition, schedule_results, expedition_dir):
    """Calculate the expedition cost, write it to a file, and print summary."""
    assert expedition.schedule.waypoints[0].time is not None, (
        "First waypoint has no time. This should not be possible as it should have been verified before."
    )
    time_past = schedule_results.time - expedition.schedule.waypoints[0].time
    cost = expedition_cost(schedule_results, time_past)
    with open(expedition_dir.joinpath("results", "cost.txt"), "w") as file:
        file.writelines(f"cost: {cost} US$")
    print(f"\nExpedition duration: {time_past}\nExpedition cost: US$ {cost:,.0f}.")
