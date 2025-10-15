"""Schedule class."""

from __future__ import annotations

import itertools
from datetime import datetime, timedelta
from pathlib import Path
from typing import TYPE_CHECKING

import numpy as np
import pydantic
import pyproj
import yaml
from parcels import Field

from virtualship.errors import ScheduleError
from virtualship.instruments.master import InstrumentType

from .location import Location
from .space_time_region import SpaceTimeRegion

if TYPE_CHECKING:
    from parcels import FieldSet


projection: pyproj.Geod = pyproj.Geod(ellps="WGS84")


class Waypoint(pydantic.BaseModel):
    """A Waypoint to sail to with an optional time and an optional instrument."""

    location: Location
    time: datetime | None = None
    instrument: InstrumentType | list[InstrumentType] | None = None

    @pydantic.field_serializer("instrument")
    def serialize_instrument(self, instrument):
        """Ensure InstrumentType is serialized as a string (or list of strings)."""
        if isinstance(instrument, list):
            return [inst.value for inst in instrument]
        return instrument.value if instrument else None


class Schedule(pydantic.BaseModel):
    """Schedule of the virtual ship."""

    waypoints: list[Waypoint]
    space_time_region: SpaceTimeRegion | None = None

    model_config = pydantic.ConfigDict(extra="forbid")

    def to_yaml(self, file_path: str | Path) -> None:
        """
        Write schedule to yaml file.

        :param file_path: Path to the file to write to.
        """
        with open(file_path, "w") as file:
            yaml.dump(
                self.model_dump(
                    by_alias=True,
                ),
                file,
            )

    @classmethod
    def from_yaml(cls, file_path: str | Path) -> Schedule:
        """
        Load schedule from yaml file.

        :param file_path: Path to the file to load from.
        :returns: The schedule.
        """
        with open(file_path) as file:
            data = yaml.safe_load(file)
        return Schedule(**data)

    def get_instruments(self) -> set[InstrumentType]:
        """
        Retrieve a set of unique instruments used in the schedule.

        This method iterates through all waypoints in the schedule and collects
        the instruments associated with each waypoint. It returns a set of unique
        instruments, either as objects or as names.

        :raises CheckpointError: If the past waypoints in the given schedule
                                 have been changed compared to the checkpoint.
        :return: set: A set of unique instruments used in the schedule.

        """
        instruments_in_schedule = []
        for waypoint in self.waypoints:
            if waypoint.instrument:
                for instrument in waypoint.instrument:
                    if instrument:
                        instruments_in_schedule.append(instrument)
        return set(instruments_in_schedule)

    def verify(
        self,
        ship_speed: float,
        input_data: Path,
        *,
        check_space_time_region: bool = False,
    ) -> None:
        """
        Verify the feasibility and correctness of the schedule's waypoints.

        This method performs several checks to ensure the schedule is valid:
        1. At least one waypoint is provided.
        2. The first waypoint has a specified time.
        3. Waypoint times are in ascending order.
        4. All waypoints are located in water (not on land).
        5. The ship can arrive on time at each waypoint given its speed.

        :param ship_speed: The ship's speed in knots.
        :param input_data: Path to input data used for bathymetry checks.
        :param check_space_time_region: Whether to check for a defined space_time_region.
        :raises ScheduleError: If any of the verification checks fail.
        :return: None. Raises exceptions if verification fails.
        """
        print("\nVerifying route... ")

        if check_space_time_region and self.space_time_region is None:
            raise ScheduleError(
                "space_time_region not found in schedule, please define it to fetch the data."
            )

        if len(self.waypoints) == 0:
            raise ScheduleError("At least one waypoint must be provided.")

        # check first waypoint has a time
        if self.waypoints[0].time is None:
            raise ScheduleError("First waypoint must have a specified time.")

        # check waypoint times are in ascending order
        timed_waypoints = [wp for wp in self.waypoints if wp.time is not None]
        checks = [
            next.time >= cur.time for cur, next in itertools.pairwise(timed_waypoints)
        ]
        if not all(checks):
            invalid_i = [i for i, c in enumerate(checks) if c]
            raise ScheduleError(
                f"Waypoint(s) {', '.join(f'#{i + 1}' for i in invalid_i)}: each waypoint should be timed after all previous waypoints",
            )

        # check if all waypoints are in water using bathymetry data
        # TODO: tests should be updated to check this!
        land_waypoints = []
        bathymetry_path = input_data.joinpath("bathymetry.nc")
        bathymetry_field = Field.from_netcdf(
            bathymetry_path,
            variables=("bathymetry", "deptho"),
            dimensions={"lon": "longitude", "lat": "latitude"},
        )
        for wp_i, wp in enumerate(self.waypoints):
            bathy = bathymetry_field.eval(
                0,  # time
                0,  # depth (surface)
                wp.location.lat,
                wp.location.lon,
            )
            if np.isnan(bathy) or bathy >= 0:
                land_waypoints.append((wp_i, wp))
        if len(land_waypoints) > 0:
            raise ScheduleError(
                f"The following waypoints are on land: {['#' + str(wp_i + 1) + ' ' + str(wp) for (wp_i, wp) in land_waypoints]}"
            )

        # check that ship will arrive on time at each waypoint (in case no unexpected event happen)
        time = self.waypoints[0].time
        for wp_i, (wp, wp_next) in enumerate(
            zip(self.waypoints, self.waypoints[1:], strict=False)
        ):
            if wp.instrument is InstrumentType.CTD:
                time += timedelta(minutes=20)

            geodinv: tuple[float, float, float] = projection.inv(
                wp.location.lon,
                wp.location.lat,
                wp_next.location.lon,
                wp_next.location.lat,
            )
            distance = geodinv[2]

            time_to_reach = timedelta(seconds=distance / ship_speed * 3600 / 1852)
            arrival_time = time + time_to_reach

            if wp_next.time is None:
                time = arrival_time
            elif arrival_time > wp_next.time:
                raise ScheduleError(
                    f"Waypoint planning is not valid: would arrive too late at waypoint number {wp_i + 2}. "
                    f"location: {wp_next.location} time: {wp_next.time} instrument: {wp_next.instrument}"
                )
            else:
                time = wp_next.time

        print("... All good to go!")


def _is_on_land_zero_uv(fieldset: FieldSet, waypoint: Waypoint) -> bool:
    """
    Check if waypoint is on land by assuming zero velocity means land.

    :param fieldset: The fieldset to sample the velocity from.
    :param waypoint: The waypoint to check.
    :returns: If the waypoint is on land.
    """
    return fieldset.UV.eval(
        0,
        fieldset.gridset.grids[0].depth[0],
        waypoint.location.lat,
        waypoint.location.lon,
        applyConversion=False,
    ) == (0.0, 0.0)
