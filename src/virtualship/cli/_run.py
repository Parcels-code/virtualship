"""do_expedition function."""

import glob
import logging
import os
import shutil
import time
from pathlib import Path

import copernicusmarine

from virtualship.expedition.simulate_schedule import (
    MeasurementsToSimulate,
    ScheduleProblem,
    simulate_schedule,
)
from virtualship.make_realistic.problems.simulator import ProblemSimulator
from virtualship.models import Checkpoint, Schedule
from virtualship.utils import (
    CHECKPOINT,
    EXPEDITION,
    PROBLEMS_ENCOUNTERED_DIR,
    PROJECTION,
    _get_expedition,
    _save_checkpoint,
    expedition_cost,
    get_instrument_class,
)

# parcels logger (suppress INFO messages to prevent log being flooded)
external_logger = logging.getLogger("parcels.tools.loggers")
external_logger.setLevel(logging.WARNING)

# copernicusmarine logger (suppress INFO messages to prevent log being flooded)
logging.getLogger("copernicusmarine").setLevel("ERROR")


def _run(
    expedition_dir: str | Path, prob_level: int, from_data: Path | None = None
) -> None:
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
        # TODO: caution, if collaborative environments (or the same machine), this will mean that multiple users share the same copernicusmarine credentials file
        # TODO: deal with this for if/when using collaborative environments (same machine) and streaming data from Copernicus Marine Service?
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

    # verify instruments_config file is consistent with schedule
    expedition.instruments_config.verify(expedition)

    # load last checkpoint
    checkpoint = _load_checkpoint(expedition_dir)
    if checkpoint is None:
        checkpoint = Checkpoint(past_schedule=Schedule(waypoints=[]))

    # verify that schedule and checkpoint match, and that problems have been resolved
    checkpoint.verify(expedition, expedition_dir)

    print("\n---- WAYPOINT VERIFICATION ----")

    expedition.schedule.verify(
        expedition.ship_config.ship_speed_knots,
        from_data=Path(from_data) if from_data else None,
    )

    # simulate the schedule
    schedule_results = simulate_schedule(
        projection=PROJECTION,
        expedition=expedition,
    )

    # handle cases where user defined schedule is incompatible (i.e. not enough time between waypoints, not problems)
    if isinstance(schedule_results, ScheduleProblem):
        print(
            f"Please update your schedule (`virtualship plan` or directly in {EXPEDITION}) and continue the expedition by executing the `virtualship run` command again.\nCheckpoint has been saved to {expedition_dir.joinpath(CHECKPOINT)}."
        )
        _save_checkpoint(
            Checkpoint(
                past_schedule=expedition.schedule,
                failed_waypoint_i=schedule_results.failed_waypoint_i,
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

    # identify instruments in expedition
    instruments_in_expedition = expedition.get_instruments()

    # unique hash for this expedition (based on waypoint locations and instrument types); used for identifying previously encountered problems; therefore new set of problems if waypoint locations or instrument types change
    expedition_hash = expedition.get_expedition_hash()

    # problems
    selected_problems_fname = "selected_problems_" + expedition_hash + ".json"

    problem_simulator = ProblemSimulator(expedition, expedition_dir)

    # re-load previously encountered, valid (same expedition as previously) problems if they exist, else select new problems and cache them
    if os.path.exists(
        expedition_dir / PROBLEMS_ENCOUNTERED_DIR / selected_problems_fname
    ):
        problems = problem_simulator.load_selected_problems(selected_problems_fname)
    else:
        problems = problem_simulator.select_problems(
            instruments_in_expedition, prob_level
        )
        if problems:
            problem_simulator.cache_selected_problems(problems, selected_problems_fname)

    # simulate measurements
    print("\nSimulating measurements. This may take a while...\n")

    for itype in instruments_in_expedition:
        if problems:  # only helpful if problems are being simulated
            print(
                f"\033[4mUp next\033[0m: {itype.name} measurements...\n"
            )  # TODO: will want to clear once simulation line is running...

        if problems:
            problem_simulator.execute(
                problems,
                instrument_type_validation=itype,
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

    if problems:
        print("\n----- RECORD OF PROBLEMS ENCOUNTERED ------")
        print(
            f"\nA record of problems encountered during the expedition is saved in: {expedition_dir.joinpath(PROBLEMS_ENCOUNTERED_DIR)}"
        )

    # delete checkpoint file (inteferes with ability to re-run expedition)
    os.remove(expedition_dir.joinpath(CHECKPOINT))

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


def _load_hashes(expedition_dir: Path) -> set[str]:
    hashes_path = expedition_dir.joinpath(PROBLEMS_ENCOUNTERED_DIR)
    if not hashes_path.exists():
        return set()
    hash_files = glob.glob(str(hashes_path / "problem_*.txt"))
    hashes = {Path(f).stem.split("_")[1] for f in hash_files}
    return hashes


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
