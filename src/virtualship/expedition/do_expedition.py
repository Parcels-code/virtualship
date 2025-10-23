"""do_expedition function."""

import os
import shutil
from pathlib import Path

import pyproj

from virtualship.cli._fetch import get_existing_download, get_space_time_region_hash
from virtualship.edito_ready.edito_working import InputData
from virtualship.models import Expedition, Schedule
from virtualship.utils import (
    CHECKPOINT,
    _get_expedition,
)

from .checkpoint import Checkpoint
from .expedition_cost import expedition_cost
from .simulate_measurements import simulate_measurements
from .simulate_schedule import ScheduleProblem, simulate_schedule

# projection used to sail between waypoints
projection = pyproj.Geod(ellps="WGS84")


def do_expedition(expedition_dir: str | Path, input_data: Path | None = None) -> None:
    """
    Perform an expedition, providing terminal feedback and file output.

    :param expedition_dir: The base directory for the expedition.
    :param input_data: Input data folder (override used for testing).
    """
    print("\n╔═════════════════════════════════════════════════╗")
    print("║          VIRTUALSHIP EXPEDITION STATUS          ║")
    print("╚═════════════════════════════════════════════════╝")

    if isinstance(expedition_dir, str):
        expedition_dir = Path(expedition_dir)

    expedition = _get_expedition(expedition_dir)

    # Verify instruments_config file is consistent with schedule
    expedition.instruments_config.verify(expedition.schedule)

    # load last checkpoint
    checkpoint = _load_checkpoint(expedition_dir)
    if checkpoint is None:
        checkpoint = Checkpoint(past_schedule=Schedule(waypoints=[]))

    # verify that schedule and checkpoint match
    checkpoint.verify(expedition.schedule)

    # load fieldsets
    loaded_input_data = _load_input_data(
        expedition_dir=expedition_dir,
        expedition=expedition,
        input_data=input_data,
    )

    print("\n---- WAYPOINT VERIFICATION ----")

    # verify schedule is valid
    expedition.schedule.verify(
        expedition.ship_config.ship_speed_knots, loaded_input_data
    )

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

    # calculate expedition cost in US$
    assert expedition.schedule.waypoints[0].time is not None, (
        "First waypoint has no time. This should not be possible as it should have been verified before."
    )
    time_past = schedule_results.time - expedition.schedule.waypoints[0].time
    cost = expedition_cost(schedule_results, time_past)
    with open(expedition_dir.joinpath("results", "cost.txt"), "w") as file:
        file.writelines(f"cost: {cost} US$")
    print(f"\nExpedition duration: {time_past}\nExpedition cost: US$ {cost:,.0f}.")

    print("\n--- MEASUREMENT SIMULATIONS ---")

    # simulate measurements
    print("\nSimulating measurements. This may take a while...\n")
    simulate_measurements(
        expedition_dir,
        expedition.instruments_config,
        loaded_input_data,
        schedule_results.measurements_to_simulate,
    )
    print("\nAll measurement simulations are complete.")

    print("\n----- EXPEDITION RESULTS ------")
    print("\nYour expedition has concluded successfully!")
    print(
        f"Your measurements can be found in the '{expedition_dir}/results' directory."
    )
    print("\n------------- END -------------\n")


def _load_input_data(
    expedition_dir: Path,
    expedition: Expedition,
    input_data: Path | None,
) -> InputData:
    """
    Load the input data.

    :param expedition_dir: Directory of the expedition.
    :param expedition: Expedition object.
    :param input_data: Folder containing input data.
    :return: InputData object.
    """
    if input_data is None:
        space_time_region_hash = get_space_time_region_hash(
            expedition.schedule.space_time_region
        )
        input_data = get_existing_download(expedition_dir, space_time_region_hash)

    # TODO not relevant if streaming data
    # assert input_data is not None, (
    #     "Input data hasn't been found. Have you run the `virtualship fetch` command?"
    # )

    return InputData.load(
        directory=input_data,
        load_adcp=expedition.instruments_config.adcp_config is not None,
        load_argo_float=expedition.instruments_config.argo_float_config is not None,
        load_ctd=expedition.instruments_config.ctd_config is not None,
        load_ctd_bgc=expedition.instruments_config.ctd_bgc_config is not None,
        load_drifter=expedition.instruments_config.drifter_config is not None,
        load_xbt=expedition.instruments_config.xbt_config is not None,
        load_ship_underwater_st=expedition.instruments_config.ship_underwater_st_config
        is not None,
        expedition=expedition,
    )


def _load_checkpoint(expedition_dir: Path) -> Checkpoint | None:
    file_path = expedition_dir.joinpath(CHECKPOINT)
    try:
        return Checkpoint.from_yaml(file_path)
    except FileNotFoundError:
        return None


def _save_checkpoint(checkpoint: Checkpoint, expedition_dir: Path) -> None:
    file_path = expedition_dir.joinpath(CHECKPOINT)
    checkpoint.to_yaml(file_path)
