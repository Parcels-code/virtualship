"""simulate_schedule function and supporting classes."""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timedelta
from typing import ClassVar

import pyproj

from virtualship.instruments.argo_float import ArgoFloat
from virtualship.instruments.ctd import CTD
from virtualship.instruments.drifter import Drifter
from virtualship.instruments.types import InstrumentType
from virtualship.instruments.xbt import XBT
from virtualship.models import (
    Expedition,
    Location,
    Spacetime,
    Waypoint,
)
from virtualship.utils import _calc_sail_time


@dataclass
class ScheduleOk:
    """Result of schedule that could be completed."""

    time: datetime
    measurements_to_simulate: MeasurementsToSimulate


@dataclass
class ScheduleProblem:
    """Result of schedule that could not be fully completed."""

    time: datetime
    failed_waypoint_i: int


@dataclass
class MeasurementsToSimulate:
    """
    The measurements to simulate, as concluded from schedule simulation.

    Provides a mapping from InstrumentType to the correct attribute name for robust access.
    """

    _instrumenttype_to_attr: ClassVar[dict] = {
        InstrumentType.ADCP: "adcps",
        InstrumentType.UNDERWATER_ST: "ship_underwater_sts",
        InstrumentType.ARGO_FLOAT: "argo_floats",
        InstrumentType.DRIFTER: "drifters",
        InstrumentType.CTD: "ctds",
        InstrumentType.XBT: "xbts",
    }

    @classmethod
    def get_attr_for_instrumenttype(cls, instrument_type):
        """Return the attribute name for a given InstrumentType."""
        return cls._instrumenttype_to_attr[instrument_type]

    adcps: list[Spacetime] = field(default_factory=list, init=False)
    ship_underwater_sts: list[Spacetime] = field(default_factory=list, init=False)
    argo_floats: list[ArgoFloat] = field(default_factory=list, init=False)
    drifters: list[Drifter] = field(default_factory=list, init=False)
    ctds: list[CTD] = field(default_factory=list, init=False)
    xbts: list[XBT] = field(default_factory=list, init=False)


def simulate_schedule(
    projection: pyproj.Geod, expedition: Expedition
) -> ScheduleOk | ScheduleProblem:
    """
    Simulate a schedule.

    :param projection: The projection to use for sailing.
    :param expedition: Expedition object containing the schedule to simulate.
    :returns: Either the results of a successfully simulated schedule, or information on where the schedule became infeasible.
    """
    return _ScheduleSimulator(projection, expedition).simulate()


class _ScheduleSimulator:
    _projection: pyproj.Geod
    _expedition: Expedition

    _time: datetime
    """Current time."""
    _location: Location
    """Current ship location."""

    _measurements_to_simulate: MeasurementsToSimulate

    _next_adcp_time: datetime
    """Next moment ADCP measurement will be done."""
    _next_ship_underwater_st_time: datetime
    """Next moment ship underwater ST measurement will be done."""

    def __init__(self, projection: pyproj.Geod, expedition: Expedition) -> None:
        self._projection = projection
        self._expedition = expedition

        assert self._expedition.schedule.waypoints[0].time is not None, (
            "First waypoint must have a time. This should have been verified before calling this function."
        )
        self._time = expedition.schedule.waypoints[0].time
        self._location = expedition.schedule.waypoints[0].location

        self._measurements_to_simulate = MeasurementsToSimulate()

        self._next_adcp_time = self._time
        self._next_ship_underwater_st_time = self._time

    def simulate(self) -> ScheduleOk | ScheduleProblem:
        # TODO: instrument config mapping (as introduced in #269) should be helpful for refactoring here (i.e. #236)...

        for wp_i, waypoint in enumerate(self._expedition.schedule.waypoints):
            # sail towards waypoint
            self._progress_time_traveling_towards(waypoint.location)

            # check if waypoint was reached in time
            # TODO: already tested in schedule.verify(), re-check here for robustness but could be removed if deemed redundant
            if waypoint.time is not None and self._time > waypoint.time:
                print(
                    f"\nWaypoint {wp_i + 1} could not be reached in time. Current time: {self._time}. Waypoint time: {waypoint.time}."
                    "\n\nHave you ensured that your schedule includes sufficient time for taking measurements, e.g. CTD casts (in addition to the time it takes to sail between waypoints)?\n"
                )
                return ScheduleProblem(self._time, wp_i)
            else:
                self._time = (
                    waypoint.time
                )  # wait at the waypoint until ship is scheduled to be there

            # note measurements made at waypoint
            time_passed = self._make_measurements(waypoint)

            # wait while measurements are being done
            self._progress_time_stationary(time_passed)

        return ScheduleOk(self._time, self._measurements_to_simulate)

    def _progress_time_traveling_towards(self, location: Location) -> None:
        """Travel from current location/waypoint to next waypoint, also mark locations and times for underway instrument measurements."""
        time_to_reach, azimuth1, ship_speed_meter_per_second = _calc_sail_time(
            self._location,
            location,
            self._expedition.ship_config.ship_speed_knots,
            self._projection,
        )
        end_time = self._time + time_to_reach
        distance_to_move = ship_speed_meter_per_second * time_to_reach.total_seconds()

        # note all ADCP measurements
        if self._expedition.instruments_config.adcp_config is not None:
            adcp_times, adcp_lons, adcp_lats = self._get_underway_measurements(
                self._expedition.instruments_config.adcp_config,
                azimuth1,
                distance_to_move,
                time_to_reach,
            )

            for time, lon, lat in zip(adcp_times, adcp_lons, adcp_lats, strict=False):
                location = Location(latitude=lat, longitude=lon)
                self._measurements_to_simulate.adcps.append(
                    Spacetime(location=location, time=time)
                )

        # note all ship underwater ST measurements
        if self._expedition.instruments_config.ship_underwater_st_config is not None:
            st_times, st_lons, st_lats = self._get_underway_measurements(
                self._expedition.instruments_config.ship_underwater_st_config,
                azimuth1,
                distance_to_move,
                time_to_reach,
            )

            for time, lon, lat in zip(st_times, st_lons, st_lats, strict=False):
                location = Location(latitude=lat, longitude=lon)
                self._measurements_to_simulate.ship_underwater_sts.append(
                    Spacetime(location=location, time=time)
                )

        self._time = end_time
        self._location = location

    def _get_underway_measurements(
        self,
        underway_instrument_config,
        azimuth: float,
        distance_to_move: float,
        time_to_reach: timedelta,
    ):
        """Get the times and locations of measurements between current location/waypoint and the next waypoint, for underway instruments."""
        period = underway_instrument_config.period
        npts = (time_to_reach.total_seconds() / period.total_seconds()) + 1
        times = [self._time + i * period for i in range(1, int(npts) + 1)]

        geodfwd = self._projection.fwd_intermediate(
            lon1=self._location.lon,
            lat1=self._location.lat,
            azi1=azimuth,
            npts=npts,
            del_s=distance_to_move / npts,
            return_back_azimuth=False,
        )

        return times, geodfwd.lons, geodfwd.lats

    def _progress_time_stationary(self, time_passed: timedelta) -> None:
        """Make ship stay at waypoint whilst instruments are deployed, also set the underway instrument measurements that are taken during this time whilst stationary."""
        end_time = self._time + time_passed

        # note all ADCP measurements (stationary at wp)
        if self._expedition.instruments_config.adcp_config is not None:
            adcp_times = self._get_underway_stationary_times(
                self._expedition.instruments_config.adcp_config, time_passed
            )

            for time in adcp_times:
                self._measurements_to_simulate.adcps.append(
                    Spacetime(location=self._location, time=time)
                )

        # note all underwater ST measurements (stationary at wp)
        if self._expedition.instruments_config.ship_underwater_st_config is not None:
            st_times = self._get_underway_stationary_times(
                self._expedition.instruments_config.ship_underwater_st_config,
                time_passed,
            )
            for time in st_times:
                self._measurements_to_simulate.ship_underwater_sts.append(
                    Spacetime(location=self._location, time=time)
                )

        self._time = end_time

    def _get_underway_stationary_times(
        self, underway_instrument_config, time_passed: timedelta
    ):
        npts = (
            time_passed.total_seconds()
            / underway_instrument_config.period.total_seconds()
        ) + 1
        return [
            self._time + i * underway_instrument_config.period
            for i in range(1, int(npts) + 1)
        ]

    def _make_measurements(self, waypoint: Waypoint) -> timedelta:
        # if there are no instruments, there is no time cost
        if waypoint.instrument is None:
            return timedelta()

        # make instruments a list even if it's only a single one
        instruments = (
            waypoint.instrument
            if isinstance(waypoint.instrument, list)
            else [waypoint.instrument]
        )

        # time costs of each measurement
        time_costs = [timedelta()]

        for instrument in instruments:
            if instrument is InstrumentType.ARGO_FLOAT:
                self._measurements_to_simulate.argo_floats.append(
                    ArgoFloat(
                        spacetime=Spacetime(self._location, self._time),
                        min_depth=self._expedition.instruments_config.argo_float_config.min_depth_meter,
                        max_depth=self._expedition.instruments_config.argo_float_config.max_depth_meter,
                        drift_depth=self._expedition.instruments_config.argo_float_config.drift_depth_meter,
                        vertical_speed=self._expedition.instruments_config.argo_float_config.vertical_speed_meter_per_second,
                        cycle_days=self._expedition.instruments_config.argo_float_config.cycle_days,
                        drift_days=self._expedition.instruments_config.argo_float_config.drift_days,
                    )
                )
                # TODO: would be good to avoid having to twice make sure that stationkeeping time is factored in; i.e. in schedule validity checks and here (and for CTDs and Drifters)
                # TODO: makes it easy to forget to update both...
                # TODO: this is likely to fall under refactoring simulate_schedule.py (i.e. #236)
                time_costs.append(
                    self._expedition.instruments_config.argo_float_config.stationkeeping_time
                )

            elif instrument is InstrumentType.CTD:
                self._measurements_to_simulate.ctds.append(
                    CTD(
                        spacetime=Spacetime(self._location, self._time),
                        min_depth=self._expedition.instruments_config.ctd_config.min_depth_meter,
                        max_depth=self._expedition.instruments_config.ctd_config.max_depth_meter,
                    )
                )
                time_costs.append(
                    self._expedition.instruments_config.ctd_config.stationkeeping_time
                )

            elif instrument is InstrumentType.DRIFTER:
                self._measurements_to_simulate.drifters.append(
                    Drifter(
                        spacetime=Spacetime(self._location, self._time),
                        depth=self._expedition.instruments_config.drifter_config.depth_meter,
                        lifetime=self._expedition.instruments_config.drifter_config.lifetime,
                    )
                )
                time_costs.append(
                    self._expedition.instruments_config.drifter_config.stationkeeping_time
                )

            elif instrument is InstrumentType.XBT:
                self._measurements_to_simulate.xbts.append(
                    XBT(
                        spacetime=Spacetime(self._location, self._time),
                        min_depth=self._expedition.instruments_config.xbt_config.min_depth_meter,
                        max_depth=self._expedition.instruments_config.xbt_config.max_depth_meter,
                        fall_speed=self._expedition.instruments_config.xbt_config.fall_speed_meter_per_second,
                        deceleration_coefficient=self._expedition.instruments_config.xbt_config.deceleration_coefficient,
                    )
                )
            else:
                raise NotImplementedError("Instrument type not supported.")

        # measurements are done simultaneously onboard, so return time of longest one
        # TODO: docs suggest that add individual instrument stationkeeping times are cumulative, which is at odds with measurements being done simultaneously onboard here
        # TODO: update one or the other?
        return max(time_costs)
