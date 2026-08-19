import logging
import os
import shutil
import sys
import time
from datetime import datetime
from pathlib import Path

import copernicusmarine

from virtualship.expedition.simulate_schedule import (
    MeasurementsToSimulate,
    ScheduleOk,
    ScheduleProblem,
    simulate_schedule,
)
from virtualship.instruments.types import InstrumentType
from virtualship.make_realistic.problems.simulator import ProblemSimulator
from virtualship.models import Checkpoint
from virtualship.models.expedition import Expedition
from virtualship.utils import (
    CACHE,
    CHECKPOINT,
    EXPEDITION,
    EXPEDITION_IDENTIFIER,
    EXPEDITION_LATEST,
    PROBLEMS_ENCOUNTERED,
    PROJECTION,
    RESULTS,
    _get_expedition,
    _save_checkpoint,
    expedition_cost,
    get_instrument_class,
)

# Suppress INFO messages from copernicusmarine and parcels loggers; prevent log flooding
logging.getLogger("parcels._logger").setLevel(logging.WARNING)
logging.getLogger("copernicusmarine").setLevel(logging.ERROR)


def _run(
    expedition_dir: str | Path,
    difficulty_level: str,
    from_data: str | Path | None = None,
) -> None:
    """Perform an expedition, providing terminal feedback and file output."""
    start_time = time.time()
    expedition_dir = Path(expedition_dir)
    data_path = Path(from_data) if from_data else None

    print("[TIMER] Expedition started...")
    _print_banner()

    if not data_path:
        _ensure_copernicus_auth()

    expedition = _get_expedition(expedition_dir)
    cache_dir = expedition_dir / CACHE
    results_dir = expedition_dir / RESULTS

    expedition_id = _unique_id(expedition, cache_dir, expedition_dir)
    problems_dir = cache_dir / PROBLEMS_ENCOUNTERED.format(expedition_id=expedition_id)

    expedition.instruments_config.verify(expedition)
    problem_simulator = ProblemSimulator(expedition, expedition_dir, difficulty_level)

    checkpoint = _load_checkpoint(expedition_dir)
    if checkpoint is not None:
        checkpoint.verify_past_schedule(expedition.schedule)
        problem_simulator.verify_problem_resolution(checkpoint)

    print("\n---- WAYPOINT VERIFICATION ----")
    expedition.schedule.verify(
        expedition.ship_config.ship_speed_knots,
        expedition.instruments_config,
        from_data=data_path,
    )

    schedule_results = simulate_schedule(
        projection=PROJECTION,
        expedition=expedition,
    )

    if isinstance(schedule_results, ScheduleProblem):
        _handle_schedule_failure(schedule_results, expedition, expedition_dir)
        return

    _prepare_results_directory(results_dir, is_new_run=(checkpoint is None))

    print("\n----- EXPEDITION SUMMARY ------")
    _write_expedition_cost(expedition, schedule_results, expedition_dir)

    print("\n--- MEASUREMENT SIMULATIONS ---")
    instruments_in_expedition = expedition.get_instruments()

    print("\nSimulating measurements. This may take a while...\n")
    try:
        _simulate_measurements(
            expedition=expedition,
            schedule_results=schedule_results,
            instruments=instruments_in_expedition,
            problem_simulator=problem_simulator,
            data_path=data_path,
        )
    except Exception as e:
        _cleanup_on_failure(problems_dir, expedition_dir)
        raise RuntimeError(
            f"An unexpected error occurred while simulating measurements: {e}. "
            "Please report this issue to the VirtualShip issue tracker at: "
            "https://github.com/OceanParcels/virtualship/issues"
        ) from e

    print("\nAll measurement simulations are complete.")

    problem_simulator.create_post_expedition_report()
    _conclude_expedition(expedition_dir, difficulty_level)

    elapsed = time.time() - start_time
    print(f"[TIMER] Expedition completed in {elapsed / 60.0:.2f} minutes.")


# =====================================================
# SECTION: helpers
# =====================================================


def _print_banner() -> None:
    print("\n╔═════════════════════════════════════════════════╗")
    print("║          VIRTUALSHIP EXPEDITION STATUS          ║")
    print("╚═════════════════════════════════════════════════╝")


def _ensure_copernicus_auth() -> None:
    creds_file = Path(
        os.path.expandvars("$HOME/.copernicusmarine/.copernicusmarine-credentials")
    )
    if not (creds_file.is_file() and creds_file.stat().st_size > 0):
        print(
            "\nPlease enter your log in details for the Copernicus Marine Service "
            "(only necessary the first time you run VirtualShip).\n\n"
            "If you have not registered yet, please do so at https://marine.copernicus.eu/.\n\n"
            "If you did not expect to see this message, and intended to use pre-downloaded "
            "data instead of streaming via Copernicus Marine, please use the '--from-data' option.\n"
        )
        copernicusmarine.login()


def _unique_id(expedition: Expedition, cache_dir: Path, expedition_dir: Path) -> str:
    cache_dir.mkdir(exist_ok=True)
    id_path = cache_dir / EXPEDITION_IDENTIFIER
    last_expedition_path = cache_dir / EXPEDITION_LATEST
    checkpoint_path = expedition_dir / CHECKPOINT
    new_id = datetime.now().strftime("%Y%m%d%H%M%S")

    if not id_path.exists():
        id_path.write_text(new_id)
        return new_id

    previous_id = id_path.read_text().strip()

    if checkpoint_path.exists():
        return previous_id

    if not last_expedition_path.exists():
        id_path.write_text(new_id)
        return new_id

    last_expedition = Expedition.from_yaml(last_expedition_path)
    added_instruments = set(expedition.get_instruments()) - set(
        last_expedition.get_instruments()
    )

    if added_instruments:
        id_path.write_text(new_id)
        return new_id

    return previous_id


def _handle_schedule_failure(
    schedule_results: ScheduleProblem, expedition: Expedition, expedition_dir: Path
) -> None:
    print(
        f"Please update your schedule (`virtualship plan` or directly in {EXPEDITION}) "
        "and continue the expedition by executing the `virtualship run` command again.\n"
        f"Checkpoint has been saved to {expedition_dir / CHECKPOINT}."
    )
    _save_checkpoint(
        Checkpoint(
            past_schedule=expedition.schedule,
            failed_wp_i=schedule_results.failed_wp,
        ),
        expedition_dir,
    )


def _prepare_results_directory(results_dir: Path, is_new_run: bool) -> None:
    if is_new_run and results_dir.exists():
        _warn_overwrite_results_dir(results_dir)
        shutil.rmtree(results_dir)
    results_dir.mkdir(parents=True, exist_ok=True)


def _simulate_measurements(
    expedition: Expedition,
    schedule_results: ScheduleOk | ScheduleProblem,
    instruments: set[InstrumentType],
    problem_simulator: ProblemSimulator,
    data_path: Path | None,
) -> None:
    for itype in instruments:
        problem_simulator.execute_for_instrument(itype)

        instrument_class = get_instrument_class(itype)
        measurements = getattr(
            schedule_results.measurements_to_simulate,
            MeasurementsToSimulate.get_attr_for_instrumenttype(itype),
        )

        instrument = instrument_class(expedition=expedition, from_data=data_path)
        instrument.execute(
            measurements=measurements,
            out_path=expedition.expedition_dir
            / RESULTS
            / f"{itype.name.lower()}.parquet",
        )


def _cleanup_on_failure(problems_dir: Path, expedition_dir: Path) -> None:
    if problems_dir.exists():
        shutil.rmtree(problems_dir)
    checkpoint_file = expedition_dir / CHECKPOINT
    if checkpoint_file.exists():
        checkpoint_file.unlink()


def _conclude_expedition(
    expedition_dir: Path,
    difficulty_level: str,
) -> None:
    print("\n----- EXPEDITION RESULTS ------")
    print("\nYour expedition has concluded successfully!")
    print(
        f"Your measurements can be found in the '{expedition_dir / RESULTS}' directory."
    )

    checkpoint_path = expedition_dir / CHECKPOINT
    if checkpoint_path.exists():
        checkpoint_path.unlink()

    cache_dir = expedition_dir / CACHE
    if difficulty_level == "easy" and cache_dir.exists():
        shutil.rmtree(cache_dir)

    print("\n------------- END -------------\n")


def _warn_overwrite_results_dir(results_dir: Path) -> None:
    print(
        f"\nWARNING: The '{results_dir}' directory already exists and will be overwritten. "
        "If you want to keep previous results, move or rename the directory before re-running.\n"
    )
    decision = input("Overwrite existing results? (y/n): ")
    if decision.lower() != "y":
        print("Expedition run cancelled by user.")
        sys.exit(0)
    print("Continuing with expedition run and overwriting existing results...")


def _load_checkpoint(expedition_dir: Path) -> Checkpoint | None:
    try:
        return Checkpoint.from_yaml(expedition_dir / CHECKPOINT)
    except FileNotFoundError:
        return None


def _write_expedition_cost(
    expedition: Expedition,
    schedule_results: ScheduleOk | ScheduleProblem,
    expedition_dir: Path,
) -> None:
    first_wp = expedition.schedule.waypoints[0]
    assert first_wp.time is not None, "First waypoint has no time."

    time_past = schedule_results.time - first_wp.time
    cost = expedition_cost(schedule_results, time_past)

    cost_file = expedition_dir / RESULTS / "cost.txt"
    cost_file.write_text(f"cost: {cost} US$")

    print(f"\nExpedition duration: {time_past}\nExpedition cost: US$ {cost:,.0f}.")
