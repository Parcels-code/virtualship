"""Checkpoint class."""

from __future__ import annotations

import json
from datetime import timedelta
from pathlib import Path

import pydantic
import yaml

from virtualship.errors import CheckpointError
from virtualship.instruments.types import InstrumentType
from virtualship.models.expedition import Schedule
from virtualship.utils import EXPEDITION, PROBLEMS_ENCOUNTERED_DIR


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

    def verify(self, schedule: Schedule, expedition_dir: Path) -> None:
        """
        Verify that the given schedule matches the checkpoint's past schedule , and/or that any problem has been resolved.

        Addresses changes made by the user in response to both i) scheduling issues arising for not enough time for the ship to travel between waypoints, and ii) problems encountered during simulation.
        """
        # 1) check that past waypoints have not been changed, unless is a pre-departure problem
        if self.failed_waypoint_i is None:
            pass
        elif (
            # TODO: double check this still works as intended for the user defined schedule with not enough time between waypoints case
            not schedule.waypoints[: int(self.failed_waypoint_i)]
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
                with open(file) as f:
                    problem = json.load(f)
                    if problem["resolved"]:
                        continue
                    elif not problem["resolved"]:
                        # check if delay has been accounted for in the schedule
                        delay_duration = timedelta(
                            hours=float(problem["delay_duration_hours"])
                        )  # delay associated with the problem
                        waypoint_range = (
                            range(len(self.past_schedule.waypoints))
                            if self.failed_waypoint_i is None
                            else range(
                                int(self.failed_waypoint_i), len(schedule.waypoints)
                            )
                        )
                        time_deltas = [
                            schedule.waypoints[i].time
                            - self.past_schedule.waypoints[i].time
                            for i in waypoint_range
                        ]  # difference in time between the two schedules from the failed waypoint onwards

                        if all(td >= delay_duration for td in time_deltas):
                            print(
                                "\n\n🎉 Previous problem has been resolved in the schedule.\n"
                            )

                            # save back to json file changing the resolved status to True
                            problem["resolved"] = True
                            with open(file, "w") as f_out:
                                json.dump(problem, f_out, indent=4)

                        else:
                            affected_waypoints = (
                                "all waypoints"
                                if self.failed_waypoint_i is None
                                else f"waypoint {int(self.failed_waypoint_i) + 1} onwards"
                            )
                            raise CheckpointError(
                                f"The problem encountered in previous simulation has not been resolved in the schedule! Please adjust the schedule to account for delays caused by the problem (by using `virtualship plan` or directly editing the {EXPEDITION} file).\n"
                                f"The problem was associated with a delay duration of {problem['delay_duration_hours']} hours affecting {affected_waypoints}.",
                            )

                        # only handle the first unresolved problem found; others will be handled in subsequent runs but are not yet known to the user
                        break
