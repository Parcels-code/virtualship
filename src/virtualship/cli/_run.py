"""do_expedition function."""

import logging
import os
import shutil
import time
from pathlib import Path

import copernicusmarine
import pyproj

from virtualship.expedition.simulate_schedule import (
    MeasurementsToSimulate,
    ScheduleProblem,
    simulate_schedule,
)
from virtualship.make_realistic.problems import ProblemSimulator
from virtualship.models import Schedule
from virtualship.models.checkpoint import Checkpoint
from virtualship.utils import (
    CHECKPOINT,
    _get_expedition,
    expedition_cost,
    get_instrument_class,
)

# projection used to sail between waypoints
projection = pyproj.Geod(ellps="WGS84")


# parcels logger (suppress INFO messages to prevent log being flooded)
external_logger = logging.getLogger("parcels.tools.loggers")
external_logger.setLevel(logging.WARNING)

# copernicusmarine logger (suppress INFO messages to prevent log being flooded)
logging.getLogger("copernicusmarine").setLevel("ERROR")


def _run(expedition_dir: str | Path, from_data: Path | None = None) -> None:
    """
    Perform an expedition, providing terminal feedback and file output.

    :param expedition_dir: The base directory for the expedition.
    """
    # start timing
    start_time = time.time()
    print("[TIMER] Expedition started...")

    print("\n╔═════════════════════════════════════════════════╗")
    print("║          VIRTUALSHIP EXPEDITION STATUS          ║")
    print("╚═════════════════════════════════════════════════╝")

    if from_data is None:
        # TODO: caution, if collaborative environments, will this mean everyone uses the same credentials file?
        # TODO: need to think about how to deal with this for when using collaborative environments AND streaming data via copernicusmarine
        COPERNICUS_CREDS_FILE = os.path.expandvars(
            "$HOME/.copernicusmarine/.copernicusmarine-credentials"
        )

        if (
            os.path.isfile(COPERNICUS_CREDS_FILE)
            and os.path.getsize(COPERNICUS_CREDS_FILE) > 0
        ):
            pass
        else:
            print(
                "\nPlease enter your log in details for the Copernicus Marine Service (only necessary the first time you run VirtualShip). \n\nIf you have not registered yet, please do so at https://marine.copernicus.eu/.\n\n"
                "If you did not expect to see this message, and intended to use pre-downloaded data instead of streaming via Copernicus Marine, please use the '--from-data' option to specify the path to the data.\n"
            )
            copernicusmarine.login()

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

    expedition.schedule.verify(
        expedition.ship_config.ship_speed_knots,
        from_data=Path(from_data) if from_data else None,
    )

    # simulate the schedule
    schedule_results = simulate_schedule(
        projection=projection,
        expedition=expedition,
    )
    if isinstance(schedule_results, ScheduleProblem):
        print(
            f"SIMULATION PAUSED: update your schedule (`virtualship plan`) and continue the expedition by executing the `virtualship run` command again.\nCheckpoint has been saved to {expedition_dir.joinpath(CHECKPOINT)}."
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

    # TODO: overview:
    # 1) determine all the general AND instrument problems which will occur across the whole expedition
    # 2) make a checker function which can be called at various points in the simulation to see if a problem occurs at that point
    # - e.g. at pre-departure, at each instrument measurement step, etc.
    # - each time a problem occurs, propagate its effects (e.g. delay), log it, save to checkpoint etc.
    # TODO: still need to incorp can_reoccur logic somewhere

    # TODO: prob_level needs to be parsed from CLI args
    problem_simulator = ProblemSimulator(expedition.schedule, prob_level=...)
    problems = problem_simulator.select_problems()

    # check for and execute pre-departure problems
    if problems:
        problem_simulator.execute(problems, pre_departure=True)

    for itype in instruments_in_expedition:
        # simulate problems (N.B. it's still possible for general problems to occur during the expedition)
        if problems:
            problem_simulator.execute(
                problems=problems,
                pre_departure=False,
                instrument_type=itype,
            )

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
            from_data=Path(from_data) if from_data is not None else None,
        )

        # execute simulation
        instrument.execute(
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

    # end timing
    end_time = time.time()
    elapsed = end_time - start_time
    print(f"[TIMER] Expedition completed in {elapsed / 60.0:.2f} minutes.")


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
