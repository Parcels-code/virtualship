"""Checkpoint class."""

from __future__ import annotations

import json
from datetime import timedelta
from pathlib import Path

import pydantic
import yaml

from virtualship.errors import CheckpointError
from virtualship.instruments.types import InstrumentType
from virtualship.models.expedition import Expedition, Schedule
from virtualship.utils import (
    EXPEDITION,
    PROBLEMS_ENCOUNTERED_DIR,
    PROJECTION,
    _calc_sail_time,
)


class _YamlDumper(yaml.SafeDumper):
    pass


_YamlDumper.add_representer(
    InstrumentType, lambda dumper, data: dumper.represent_data(data.value)
)


class Checkpoint(pydantic.BaseModel):
    """
    A checkpoint of schedule simulation.

    Copy of the schedule until where the simulation proceeded without troubles.
    """

    past_schedule: Schedule
    failed_waypoint_i: int | None = None

    def to_yaml(self, file_path: str | Path) -> None:
        """
        Write checkpoint to yaml file.

        :param file_path: Path to the file to write to.
        """
        with open(file_path, "w") as file:
            yaml.dump(self.model_dump(by_alias=True), file, Dumper=_YamlDumper)

    @classmethod
    def from_yaml(cls, file_path: str | Path) -> Checkpoint:
        """
        Load checkpoint from yaml file.

        :param file_path: Path to the file to load from.
        :returns: The checkpoint.
        """
        with open(file_path) as file:
            data = yaml.safe_load(file)
        return Checkpoint(**data)

    def verify(self, expedition: Expedition, expedition_dir: Path) -> None:
        """
        Verify that the given schedule matches the checkpoint's past schedule , and/or that any problem has been resolved.

        Addresses changes made by the user in response to both i) scheduling issues arising for not enough time for the ship to travel between waypoints, and ii) problems encountered during simulation.
        """
        new_schedule = expedition.schedule

        # 1) check that past waypoints have not been changed, unless is a pre-departure problem
        if self.failed_waypoint_i is None:
            pass
        elif (
            # TODO: double check this still works as intended for the user defined schedule with not enough time between waypoints case
            not new_schedule.waypoints[: int(self.failed_waypoint_i)]
            == self.past_schedule.waypoints[: int(self.failed_waypoint_i)]
        ):
            raise CheckpointError(
                f"Past waypoints in schedule have been changed! Restore past schedule and only change future waypoints (waypoint {int(self.failed_waypoint_i) + 1} onwards)."
            )

        # 2) check that problems have been resolved in the new schedule
        hash_fpaths = [
            str(path.resolve())
            for path in Path(expedition_dir, PROBLEMS_ENCOUNTERED_DIR).glob(
                "problem_*.json"
            )
        ]
        if len(hash_fpaths) > 0:
            for file in hash_fpaths:
                with open(file, encoding="utf-8") as f:
                    problem = json.load(f)
                if problem["resolved"]:
                    continue
                elif not problem["resolved"]:
                    # check if delay has been accounted for in the new schedule (at waypoint immediately after problem waypoint)

                    # TODO: should be that the new schedule time to reach the waypoint after the problem_waypoint should be sail_time + delay_duration < new_schedule_time_between_affected_waypoints
                    # TODO: but if it's a pre-departure problem then need to check that the whole departure time has been added on to the 1st waypoint

                    delay_duration = timedelta(
                        hours=float(problem["delay_duration_hours"])
                    )

                    # pre-departure problem: check that whole delay duration has been added to first waypoint time (by testing against past schedule)
                    if problem["problem_waypoint_i"] is None:
                        time_diff = (
                            new_schedule.waypoints[0].time
                            - self.past_schedule.waypoints[0].time
                        )
                        resolved = time_diff >= delay_duration
                    # problem at a later waypoint: check new scheduled time exceeds sail time + delay duration (rather whole delay duration add-on, as there may be _some_ contingency time already scheduled)

                    else:
                        time_delta = (
                            new_schedule.waypoints[self.failed_waypoint_i].time
                            - new_schedule.waypoints[self.failed_waypoint_i - 1].time
                        )
                        min_time_required = (
                            _calc_sail_time(
                                new_schedule.waypoints[
                                    self.failed_waypoint_i - 1
                                ].location,
                                new_schedule.waypoints[self.failed_waypoint_i].location,
                                ship_speed_knots=expedition.ship_config.ship_speed_knots,
                                projection=PROJECTION,
                            )[0]
                            + delay_duration
                        )
                        resolved = time_delta >= min_time_required

                    if resolved:
                        print(
                            "\n\n🎉 Previous problem has been resolved in the schedule.\n"
                        )

                        # save back to json file changing the resolved status to True
                        problem["resolved"] = True
                        with open(file, "w", encoding="utf-8") as f_out:
                            json.dump(problem, f_out, indent=4)

                        # only handle the first unresolved problem found; others will be handled in subsequent runs but are not yet known to the user
                        break

                    else:
                        problem_wp = (
                            "in-port"
                            if problem["problem_waypoint_i"] is None
                            else f"at waypoint {problem['problem_waypoint_i'] + 1}"
                        )
                        affected_wp = (
                            "1"
                            if problem["problem_waypoint_i"] is None
                            else f"{problem['problem_waypoint_i'] + 2}"
                        )
                        raise CheckpointError(
                            f"The problem encountered in previous simulation has not been resolved in the schedule! Please adjust the schedule to account for delays caused by the problem (by using `virtualship plan` or directly editing the {EXPEDITION} file).\n"
                            f"The problem was associated with a delay duration of {problem['delay_duration_hours']} hours {problem_wp} (meaning waypoint {affected_wp} could not be reached in time).\n"
                        )
