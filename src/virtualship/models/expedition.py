from __future__ import annotations

import itertools
from datetime import datetime, timedelta
from typing import TYPE_CHECKING

import pydantic
import pyproj
import yaml

from virtualship.errors import InstrumentsConfigError, ScheduleError
from virtualship.instruments.master import InstrumentType
from virtualship.utils import _validate_numeric_mins_to_timedelta

from .location import Location
from .space_time_region import SpaceTimeRegion

if TYPE_CHECKING:
    from parcels import FieldSet

    from virtualship.expedition.input_data import InputData


projection: pyproj.Geod = pyproj.Geod(ellps="WGS84")


class Expedition(pydantic.BaseModel):
    """Expedition class, including schedule and ship config."""

    schedule: Schedule
    instruments_config: InstrumentsConfig
    ship_config: ShipConfig

    model_config = pydantic.ConfigDict(extra="forbid")

    def to_yaml(self, file_path: str) -> None:
        """Write exepedition object to yaml file."""
        with open(file_path, "w") as file:
            yaml.dump(self.model_dump(by_alias=True), file)

    @classmethod
    def from_yaml(cls, file_path: str) -> Expedition:
        """Load config from yaml file."""
        with open(file_path) as file:
            data = yaml.safe_load(file)
        return Expedition(**data)

    def get_instruments(self) -> set[InstrumentType]:
        """Return a set of unique InstrumentType enums used in the expedition."""
        instruments_in_expedition = []
        # from waypoints
        for waypoint in self.schedule.waypoints:
            if waypoint.instrument:
                for instrument in waypoint.instrument:
                    if instrument:
                        instruments_in_expedition.append(instrument)

        # check for underway instruments and add if present in expeditions
        try:
            if self.instruments_config.adcp_config is not None:
                instruments_in_expedition.append(InstrumentType.ADCP)
            if self.instruments_config.ship_underwater_st_config is not None:
                instruments_in_expedition.append(InstrumentType.UNDERWATER_ST)
            return set(instruments_in_expedition)
        except Exception as e:
            raise InstrumentsConfigError(
                "Underway instrument config attribute(s) are missing from YAML. Must be <Instrument>Config object or None."
            ) from e


class ShipConfig(pydantic.BaseModel):
    """Configuration of the ship."""

    ship_speed_knots: float = pydantic.Field(gt=0.0)

    # TODO: room here for adding more ship config options in future PRs (e.g. max_days_at_sea)...

    model_config = pydantic.ConfigDict(extra="forbid")


class Schedule(pydantic.BaseModel):
    """Schedule of the virtual ship."""

    waypoints: list[Waypoint]
    space_time_region: SpaceTimeRegion | None = None

    model_config = pydantic.ConfigDict(extra="forbid")

    def verify(
        self,
        ship_speed: float,
        input_data: InputData | None,
        *,
        check_space_time_region: bool = False,
        ignore_missing_fieldsets: bool = False,
    ) -> None:
        """
        Verify the feasibility and correctness of the schedule's waypoints.

        This method checks various conditions to ensure the schedule is valid:
        1. At least one waypoint is provided.
        2. The first waypoint has a specified time.
        3. Waypoint times are in ascending order.
        4. All waypoints are in water (not on land).
        5. The ship can arrive on time at each waypoint given its speed.

        :param ship_speed: The ship's speed in knots.
        :param input_data: An InputData object containing fieldsets used to check if waypoints are on water.
        :param check_space_time_region: whether to check for missing space_time_region.
        :param ignore_missing_fieldsets: whether to ignore warning for missing field sets.
        :raises PlanningError: If any of the verification checks fail, indicating infeasible or incorrect waypoints.
        :raises NotImplementedError: If an instrument in the schedule is not implemented.
        :return: None. The method doesn't return a value but raises exceptions if verification fails.
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

        # check if all waypoints are in water
        # this is done by picking an arbitrary provided fieldset and checking if UV is not zero

        # get all available fieldsets
        available_fieldsets = []
        if input_data is not None:
            fieldsets = [
                input_data.adcp_fieldset,
                input_data.argo_float_fieldset,
                input_data.ctd_fieldset,
                input_data.drifter_fieldset,
                input_data.ship_underwater_st_fieldset,
            ]
            for fs in fieldsets:
                if fs is not None:
                    available_fieldsets.append(fs)

        # check if there are any fieldsets, else it's an error
        if len(available_fieldsets) == 0:
            if not ignore_missing_fieldsets:
                print(
                    "Cannot verify because no fieldsets have been loaded. This is probably "
                    "because you are not using any instruments in your schedule. This is not a problem, "
                    "but carefully check your waypoint locations manually."
                )

        else:
            # pick any
            fieldset = available_fieldsets[0]
            # get waypoints with 0 UV
            land_waypoints = [
                (wp_i, wp)
                for wp_i, wp in enumerate(self.waypoints)
                if _is_on_land_zero_uv(fieldset, wp)
            ]
            # raise an error if there are any
            if len(land_waypoints) > 0:
                raise ScheduleError(
                    f"The following waypoints are on land: {['#' + str(wp_i) + ' ' + str(wp) for (wp_i, wp) in land_waypoints]}"
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


class ArgoFloatConfig(pydantic.BaseModel):
    """Configuration for argos floats."""

    min_depth_meter: float = pydantic.Field(le=0.0)
    max_depth_meter: float = pydantic.Field(le=0.0)
    drift_depth_meter: float = pydantic.Field(le=0.0)
    vertical_speed_meter_per_second: float = pydantic.Field(lt=0.0)
    cycle_days: float = pydantic.Field(gt=0.0)
    drift_days: float = pydantic.Field(gt=0.0)


class ADCPConfig(pydantic.BaseModel):
    """Configuration for ADCP instrument."""

    max_depth_meter: float = pydantic.Field(le=0.0)
    num_bins: int = pydantic.Field(gt=0.0)
    period: timedelta = pydantic.Field(
        serialization_alias="period_minutes",
        validation_alias="period_minutes",
        gt=timedelta(),
    )

    model_config = pydantic.ConfigDict(populate_by_name=True)

    @pydantic.field_serializer("period")
    def _serialize_period(self, value: timedelta, _info):
        return value.total_seconds() / 60.0

    @pydantic.field_validator("period", mode="before")
    def _validate_period(cls, value: int | float | timedelta) -> timedelta:
        return _validate_numeric_mins_to_timedelta(value)


class CTDConfig(pydantic.BaseModel):
    """Configuration for CTD instrument."""

    stationkeeping_time: timedelta = pydantic.Field(
        serialization_alias="stationkeeping_time_minutes",
        validation_alias="stationkeeping_time_minutes",
        gt=timedelta(),
    )
    min_depth_meter: float = pydantic.Field(le=0.0)
    max_depth_meter: float = pydantic.Field(le=0.0)

    model_config = pydantic.ConfigDict(populate_by_name=True)

    @pydantic.field_serializer("stationkeeping_time")
    def _serialize_stationkeeping_time(self, value: timedelta, _info):
        return value.total_seconds() / 60.0

    @pydantic.field_validator("stationkeeping_time", mode="before")
    def _validate_stationkeeping_time(cls, value: int | float | timedelta) -> timedelta:
        return _validate_numeric_mins_to_timedelta(value)


class CTD_BGCConfig(pydantic.BaseModel):
    """Configuration for CTD_BGC instrument."""

    stationkeeping_time: timedelta = pydantic.Field(
        serialization_alias="stationkeeping_time_minutes",
        validation_alias="stationkeeping_time_minutes",
        gt=timedelta(),
    )
    min_depth_meter: float = pydantic.Field(le=0.0)
    max_depth_meter: float = pydantic.Field(le=0.0)

    model_config = pydantic.ConfigDict(populate_by_name=True)

    @pydantic.field_serializer("stationkeeping_time")
    def _serialize_stationkeeping_time(self, value: timedelta, _info):
        return value.total_seconds() / 60.0

    @pydantic.field_validator("stationkeeping_time", mode="before")
    def _validate_stationkeeping_time(cls, value: int | float | timedelta) -> timedelta:
        return _validate_numeric_mins_to_timedelta(value)


class ShipUnderwaterSTConfig(pydantic.BaseModel):
    """Configuration for underwater ST."""

    period: timedelta = pydantic.Field(
        serialization_alias="period_minutes",
        validation_alias="period_minutes",
        gt=timedelta(),
    )

    model_config = pydantic.ConfigDict(populate_by_name=True)

    @pydantic.field_serializer("period")
    def _serialize_period(self, value: timedelta, _info):
        return value.total_seconds() / 60.0

    @pydantic.field_validator("period", mode="before")
    def _validate_period(cls, value: int | float | timedelta) -> timedelta:
        return _validate_numeric_mins_to_timedelta(value)


class DrifterConfig(pydantic.BaseModel):
    """Configuration for drifters."""

    depth_meter: float = pydantic.Field(le=0.0)
    lifetime: timedelta = pydantic.Field(
        serialization_alias="lifetime_minutes",
        validation_alias="lifetime_minutes",
        gt=timedelta(),
    )

    model_config = pydantic.ConfigDict(populate_by_name=True)

    @pydantic.field_serializer("lifetime")
    def _serialize_lifetime(self, value: timedelta, _info):
        return value.total_seconds() / 60.0

    @pydantic.field_validator("lifetime", mode="before")
    def _validate_lifetime(cls, value: int | float | timedelta) -> timedelta:
        return _validate_numeric_mins_to_timedelta(value)


class XBTConfig(pydantic.BaseModel):
    """Configuration for xbt instrument."""

    min_depth_meter: float = pydantic.Field(le=0.0)
    max_depth_meter: float = pydantic.Field(le=0.0)
    fall_speed_meter_per_second: float = pydantic.Field(gt=0.0)
    deceleration_coefficient: float = pydantic.Field(gt=0.0)


class InstrumentsConfig(pydantic.BaseModel):
    # TODO: refactor potential for this? Move explicit instrument_config's away from models/ dir?
    """Configuration of instruments."""

    argo_float_config: ArgoFloatConfig | None = None
    """
    Argo float configuration.

    If None, no argo floats can be deployed.
    """

    adcp_config: ADCPConfig | None = None
    """
    ADCP configuration.

    If None, no ADCP measurements will be performed.
    """

    ctd_config: CTDConfig | None = None
    """
    CTD configuration.

    If None, no CTDs can be cast.
    """

    ctd_bgc_config: CTD_BGCConfig | None = None
    """
    CTD_BGC configuration.

    If None, no BGC CTDs can be cast.
    """

    ship_underwater_st_config: ShipUnderwaterSTConfig | None = None
    """
    Ship underwater salinity temperature measurementconfiguration.

    If None, no ST measurements will be performed.
    """

    drifter_config: DrifterConfig | None = None
    """
    Drifter configuration.

    If None, no drifters can be deployed.
    """

    xbt_config: XBTConfig | None = None
    """
    XBT configuration.

    If None, no XBTs can be cast.
    """

    model_config = pydantic.ConfigDict(extra="forbid")

    def verify(self, expedition: Expedition) -> None:
        """
        Verify instrument configurations against the schedule.

        Removes instrument configs not present in the schedule and checks that all scheduled instruments are configured.
        Raises ConfigError if any scheduled instrument is missing a config.
        """
        instruments_in_expedition = expedition.get_instruments()
        instrument_config_map = {
            InstrumentType.ARGO_FLOAT: "argo_float_config",
            InstrumentType.DRIFTER: "drifter_config",
            InstrumentType.XBT: "xbt_config",
            InstrumentType.CTD: "ctd_config",
            InstrumentType.CTD_BGC: "ctd_bgc_config",
            InstrumentType.ADCP: "adcp_config",
            InstrumentType.UNDERWATER_ST: "ship_underwater_st_config",
        }
        # Remove configs for unused instruments
        for inst_type, config_attr in instrument_config_map.items():
            if (
                hasattr(self, config_attr)
                and inst_type not in instruments_in_expedition
            ):
                print(
                    f"{inst_type.value} configuration provided but not in schedule. Removing config."
                )
                setattr(self, config_attr, None)
        # Check all scheduled instruments are configured
        for inst_type in instruments_in_expedition:
            config_attr = instrument_config_map.get(inst_type)
            if (
                not config_attr
                or not hasattr(self, config_attr)
                or getattr(self, config_attr) is None
            ):
                raise InstrumentsConfigError(
                    f"Expedition includes instrument '{inst_type.value}', but instruments_config does not provide configuration for it."
                )


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
