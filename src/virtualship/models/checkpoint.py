"""Checkpoint class."""

from __future__ import annotations

from datetime import timedelta
from pathlib import Path

import pydantic
import yaml

from virtualship.errors import CheckpointError
from virtualship.instruments.types import InstrumentType
from virtualship.models.expedition import Expedition, Port, Schedule
from virtualship.utils import (
    EXPEDITION,
    PROJECTION,
    _calc_sail_time,
    _calc_wp_stationkeeping_time,
    _get_public_wp,
    _read_json,
    _write_json,
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
    problem_wp_i: int | None = None

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

    def verify(self, expedition: Expedition, problems_dir: Path) -> None:
        """
        Verify that the given schedule matches the checkpoint's past schedule , and/or that any problem has been resolved.

        Addresses changes made by the user in response to both i) scheduling issues arising for not enough time for the ship to travel between waypoints, and ii) problems encountered during simulation.
        """
        new_schedule = expedition.schedule

        # problem_wp_i is None for a pre-departure problem where the departure port is an inactive placeholder
        # so there is no real problem waypoint to anchor timing calculations to
        has_problem_location = self.problem_wp_i is not None
        problem_wp_i = self.problem_wp_i if has_problem_location else 0

        # failed waypoint is the waypoint immediately *after* the problem waypoint (i.e. the one that will not be reached in time)
        failed_wp_i = problem_wp_i + 1

        # public waypoint number of problem and failed waypoints, for use in error messages
        public_problem_wp = (
            _get_public_wp(problem_wp_i, self.past_schedule.waypoints)
            if has_problem_location
            else None
        )
        public_failed_wp = _get_public_wp(failed_wp_i, self.past_schedule.waypoints)

        # 1) check that past waypoints have not been changed (up to but not including failed_wp)
        if (
            not new_schedule.waypoints[:failed_wp_i]
            == self.past_schedule.waypoints[:failed_wp_i]
        ):
            raise CheckpointError(
                f"Past waypoints in schedule have been changed! Restore past schedule and only change future waypoints (waypoint {public_failed_wp} onwards)."
            )

        # 2) check that problems have been resolved in the new schedule
        failed_waypoint = new_schedule.waypoints[failed_wp_i]

        if has_problem_location:
            problem_waypoint = new_schedule.waypoints[problem_wp_i]

            stationkeeping_time = (
                _calc_wp_stationkeeping_time(problem_waypoint.instrument, expedition)
                if not isinstance(problem_waypoint, Port)
                else timedelta(0)
            )

            sail_time = _calc_sail_time(
                problem_waypoint.location,
                failed_waypoint.location,
                ship_speed_knots=expedition.ship_config.ship_speed_knots,
                projection=PROJECTION,
            )[0]

            available_time = failed_waypoint.time - problem_waypoint.time
            base_time = problem_waypoint.time
            fixed_delay_offset = sail_time + stationkeeping_time
        else:
            # no departure location/time to sail from (departure port is an inactive placeholder)
            base_time = self.past_schedule.waypoints[failed_wp_i].time
            available_time = failed_waypoint.time - base_time
            fixed_delay_offset = timedelta(0)

        hash_fpaths = [
            str(path.resolve()) for path in problems_dir.glob("problem_*.json")
        ]

        for file in hash_fpaths:
            problem = _read_json(file)

            # continue if problem is already resolved, else perform checks to see if delay is accounted for
            if problem["resolved"]:
                continue

            delay_duration = timedelta(hours=float(problem["delay_duration_hours"]))
            min_time_required = fixed_delay_offset + delay_duration
            expected_arrival = base_time + min_time_required

            if available_time >= min_time_required:
                print("\n\n🎉 Previous problem has been resolved in the schedule.\n")

                # save back to json file changing the resolved status to True
                problem["resolved"] = True
                _write_json(file, problem)

                # only handle the first unresolved problem found; others will be handled in subsequent runs but are not yet known to the user
                break

            else:
                problem_wp_str = (
                    "in-port"
                    if public_problem_wp is None
                    else f"at waypoint {public_problem_wp}"
                )

                raise CheckpointError(
                    f"The problem encountered in previous simulation has not been resolved in the schedule! Please adjust the schedule to account for delays caused by the problem (by using `virtualship plan` or directly editing the {EXPEDITION} file).\n\n"
                    f"The problem was associated with a delay duration of {problem['delay_duration_hours']} hours {problem_wp_str} (meaning waypoint {public_failed_wp} could not be reached in time). "
                    f"Currently, the ship would reach waypoint {public_failed_wp} at {expected_arrival}, but the scheduled time is {failed_waypoint.time}."
                    + (
                        f"\n\nHint: don't forget to factor in the time required to deploy the instruments {problem_wp_str} when rescheduling waypoint {public_failed_wp}."
                        if public_problem_wp is not None
                        else ""
                    )
                )
