from __future__ import annotations

import itertools
from datetime import datetime, timedelta
from pathlib import Path
from typing import ClassVar

import numpy as np
import pydantic
import pyproj
import yaml

from virtualship.errors import InstrumentsConfigError, ScheduleError
from virtualship.instruments.sensors import SENSOR_REGISTRY, SensorType, _Sensor
from virtualship.instruments.types import InstrumentType
from virtualship.utils import (
    _calc_sail_time,
    _calc_wp_stationkeeping_time,
    _get_bathy_data,
    _get_waypoint_latlons,
    _validate_numeric_to_timedelta,
    get_supported_sensors,
    register_instrument_config,
)

from .location import Location

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
            return sorted(set(instruments_in_expedition), key=lambda x: x.name)
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

    model_config = pydantic.ConfigDict(extra="forbid")

    def verify(
        self,
        ship_speed: float,
        instruments_config: InstrumentsConfig,
        ignore_land_test: bool = False,
        *,
        from_data: Path | None = None,
    ) -> None:
        """
        Verify the feasibility and correctness of the schedule's waypoints.

        This method checks various conditions to ensure the schedule is valid:
        1. At least one waypoint is provided.
        2. The first waypoint has a specified time.
        3. Waypoint times are in ascending order.
        4. All waypoints are in water (not on land).
        5. The ship can arrive on time at each waypoint given its speed.
        """
        print("\nVerifying route... ")

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
        land_waypoints = []
        if not ignore_land_test:
            try:
                wp_lats, wp_lons = _get_waypoint_latlons(self.waypoints)
                bathymetry_field = _get_bathy_data(
                    min(wp_lats),
                    max(wp_lats),
                    min(wp_lons),
                    max(wp_lons),
                    from_data=from_data,
                ).bathymetry
            except Exception as e:
                raise ScheduleError(
                    f"Problem loading bathymetry data (used to verify waypoints are in water) directly via copernicusmarine. \n\n original message: {e}"
                ) from e

            for wp_i, wp in enumerate(self.waypoints):
                try:
                    value = bathymetry_field.eval(
                        0,  # time
                        0,  # depth (surface)
                        wp.location.lat,
                        wp.location.lon,
                    )
                    if value == 0.0 or (isinstance(value, float) and np.isnan(value)):
                        land_waypoints.append((wp_i, wp))
                except Exception as e:
                    raise ScheduleError(
                        f"Waypoint #{wp_i + 1} at location {wp.location} could not be evaluated against bathymetry data. \n\n Original error: {e}"
                    ) from e

            if len(land_waypoints) > 0:
                raise ScheduleError(
                    f"The following waypoint(s) throw(s) error(s): {['#' + str(wp_i + 1) + ' ' + str(wp) for (wp_i, wp) in land_waypoints]}\n\nINFO: They are likely on land (bathymetry data cannot be interpolated to their location(s)).\n"
                )

        # check that ship will arrive on time at each waypoint (in case no unexpected event happen)
        time = self.waypoints[0].time
        for wp_i, (wp, wp_next) in enumerate(
            zip(self.waypoints, self.waypoints[1:], strict=False)
        ):
            stationkeeping_time = _calc_wp_stationkeeping_time(
                wp.instrument, instruments_config
            )

            time_to_reach = _calc_sail_time(
                wp.location,
                wp_next.location,
                ship_speed,
                projection,
            )[0]

            arrival_time = time + time_to_reach + stationkeeping_time

            if wp_next.time is None:
                time = arrival_time
            elif arrival_time > wp_next.time:
                raise ScheduleError(
                    f"Waypoint planning is not valid: would arrive too late at waypoint {wp_i + 2}. "
                    f"Location: {wp_next.location} Time: {wp_next.time}. "
                    f"Currently projected to arrive at: {arrival_time}."
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


##


class _InstrumentConfigMixin(pydantic.BaseModel):
    """Serialisation, validation and variable mapping inheritance across instrument configs."""

    _instrument_type: ClassVar[InstrumentType]
    _instrument_name: ClassVar[str]

    @pydantic.field_validator("sensors", mode="after", check_fields=False)
    @classmethod
    def _check_sensors(cls, value) -> list[SensorConfig]:
        return SensorConfig.check_compatibility(
            value, cls._instrument_type, cls._instrument_name
        )

    @pydantic.field_serializer("sensors", check_fields=False)
    def _serialize_sensors(self, value: list[SensorConfig], _info):
        return SensorConfig.serialize_list(value)

    def active_variables(self) -> dict[str, str]:
        """FieldSet-key → Copernicus-variable mapping for enabled sensors."""
        return SensorConfig.build_variables(self.sensors)

    @pydantic.field_serializer("stationkeeping_time", "period", check_fields=False)
    def _serialize_minutes(self, value: timedelta, _info) -> float:
        return value.total_seconds() / 60.0

    @pydantic.field_validator(
        "stationkeeping_time", "period", mode="before", check_fields=False
    )
    @classmethod
    def _validate_minutes(cls, value: int | float | timedelta) -> timedelta:
        return _validate_numeric_to_timedelta(value, "minutes")

    @pydantic.field_serializer("lifetime", check_fields=False)
    def _serialize_lifetime(self, value: timedelta, _info) -> float:
        return value.total_seconds() / 86400.0  # [days]

    @pydantic.field_validator("lifetime", mode="before", check_fields=False)
    @classmethod
    def _validate_lifetime(cls, value: int | float | timedelta) -> timedelta:
        return _validate_numeric_to_timedelta(value, "days")


@register_instrument_config(InstrumentType.ARGO_FLOAT)
class ArgoFloatConfig(_InstrumentConfigMixin, pydantic.BaseModel):
    """Configuration for argos floats."""

    _instrument_type: ClassVar[InstrumentType] = InstrumentType.ARGO_FLOAT
    _instrument_name: ClassVar[str] = "ArgoFloat"

    min_depth_meter: float = pydantic.Field(le=0.0)
    max_depth_meter: float = pydantic.Field(le=0.0)
    drift_depth_meter: float = pydantic.Field(le=0.0)
    vertical_speed_meter_per_second: float = pydantic.Field(lt=0.0)
    cycle_days: float = pydantic.Field(gt=0.0)
    drift_days: float = pydantic.Field(gt=0.0)
    lifetime: timedelta = pydantic.Field(
        serialization_alias="lifetime_days",
        validation_alias="lifetime_days",
        gt=timedelta(),
    )

    stationkeeping_time: timedelta = pydantic.Field(
        serialization_alias="stationkeeping_time_minutes",
        validation_alias="stationkeeping_time_minutes",
        gt=timedelta(),
    )

    sensors: list[SensorConfig] = pydantic.Field(
        default_factory=lambda: [
            SensorConfig(sensor_type=SensorType.TEMPERATURE),
            SensorConfig(sensor_type=SensorType.SALINITY),
        ],
        description=(
            "Sensors fitted to the Argo float. Supported: TEMPERATURE, SALINITY. "
        ),
    )

    model_config = pydantic.ConfigDict(populate_by_name=True)


@register_instrument_config(InstrumentType.ADCP)
class ADCPConfig(_InstrumentConfigMixin, pydantic.BaseModel):
    """Configuration for ADCP instrument."""

    _instrument_type: ClassVar[InstrumentType] = InstrumentType.ADCP
    _instrument_name: ClassVar[str] = "ADCP"

    max_depth_meter: float = pydantic.Field(le=0.0)
    num_bins: int = pydantic.Field(gt=0.0)
    period: timedelta = pydantic.Field(
        serialization_alias="period_minutes",
        validation_alias="period_minutes",
        gt=timedelta(),
    )

    sensors: list[SensorConfig] = pydantic.Field(
        default_factory=lambda: [SensorConfig(sensor_type=SensorType.VELOCITY)],
        description=(
            "Sensors fitted to the ADCP. "
            "Supported: VELOCITY (samples both U and V components in one go)."
        ),
    )

    model_config = pydantic.ConfigDict(populate_by_name=True)

    def active_variables(self) -> dict[str, str]:
        """
        FieldSet-key → Copernicus-variable mapping for enabled sensors.

        VELOCITY is a special case: one sensor provides two FieldSet variables (U and V).
        """
        variables = {}
        for sc in self.sensors:
            if sc.enabled and sc.sensor_type == SensorType.VELOCITY:
                variables["U"] = "uo"
                variables["V"] = "vo"
        return variables


@register_instrument_config(InstrumentType.CTD)
class CTDConfig(_InstrumentConfigMixin, pydantic.BaseModel):
    """Configuration for CTD instrument."""

    _instrument_type: ClassVar[InstrumentType] = InstrumentType.CTD
    _instrument_name: ClassVar[str] = "CTD"

    stationkeeping_time: timedelta = pydantic.Field(
        serialization_alias="stationkeeping_time_minutes",
        validation_alias="stationkeeping_time_minutes",
        gt=timedelta(),
    )
    min_depth_meter: float = pydantic.Field(le=0.0)
    max_depth_meter: float = pydantic.Field(le=0.0)

    sensors: list[SensorConfig] = pydantic.Field(
        default_factory=lambda: [
            SensorConfig(sensor_type=SensorType.TEMPERATURE),
            SensorConfig(sensor_type=SensorType.SALINITY),
        ],
        description=("Sensors fitted to the CTD. Supported: TEMPERATURE, SALINITY. "),
    )

    model_config = pydantic.ConfigDict(populate_by_name=True)


@register_instrument_config(InstrumentType.CTD_BGC)
class CTD_BGCConfig(_InstrumentConfigMixin, pydantic.BaseModel):
    """Configuration for CTD_BGC instrument."""

    _instrument_type: ClassVar[InstrumentType] = InstrumentType.CTD_BGC
    _instrument_name: ClassVar[str] = "CTD_BGC"

    stationkeeping_time: timedelta = pydantic.Field(
        serialization_alias="stationkeeping_time_minutes",
        validation_alias="stationkeeping_time_minutes",
        gt=timedelta(),
    )
    min_depth_meter: float = pydantic.Field(le=0.0)
    max_depth_meter: float = pydantic.Field(le=0.0)

    sensors: list[SensorConfig] = pydantic.Field(
        default_factory=lambda: [
            SensorConfig(sensor_type=SensorType.OXYGEN),
            SensorConfig(sensor_type=SensorType.CHLOROPHYLL),
            SensorConfig(sensor_type=SensorType.NITRATE),
            SensorConfig(sensor_type=SensorType.PHOSPHATE),
            SensorConfig(sensor_type=SensorType.PH),
            SensorConfig(sensor_type=SensorType.PHYTOPLANKTON),
            SensorConfig(sensor_type=SensorType.PRIMARY_PRODUCTION),
        ],
        description=(
            "Sensors fitted to the BGC CTD. "
            "Supported: OXYGEN, CHLOROPHYLL, NITRATE, PHOSPHATE, PH, PHYTOPLANKTON, PRIMARY_PRODUCTION. "
        ),
    )

    model_config = pydantic.ConfigDict(populate_by_name=True)


@register_instrument_config(InstrumentType.UNDERWATER_ST)
class ShipUnderwaterSTConfig(_InstrumentConfigMixin, pydantic.BaseModel):
    """Configuration for underwater ST."""

    _instrument_type: ClassVar[InstrumentType] = InstrumentType.UNDERWATER_ST
    _instrument_name: ClassVar[str] = "Underwater ST"

    period: timedelta = pydantic.Field(
        serialization_alias="period_minutes",
        validation_alias="period_minutes",
        gt=timedelta(),
    )

    sensors: list[SensorConfig] = pydantic.Field(
        default_factory=lambda: [
            SensorConfig(sensor_type=SensorType.TEMPERATURE),
            SensorConfig(sensor_type=SensorType.SALINITY),
        ],
        description=(
            "Sensors fitted to the underway ST. Supported: TEMPERATURE, SALINITY. "
        ),
    )

    model_config = pydantic.ConfigDict(populate_by_name=True)


@register_instrument_config(InstrumentType.DRIFTER)
class DrifterConfig(_InstrumentConfigMixin, pydantic.BaseModel):
    """Configuration for drifters."""

    _instrument_type: ClassVar[InstrumentType] = InstrumentType.DRIFTER
    _instrument_name: ClassVar[str] = "Drifter"

    depth_meter: float = pydantic.Field(le=0.0)
    lifetime: timedelta = pydantic.Field(
        serialization_alias="lifetime_days",
        validation_alias="lifetime_days",
        gt=timedelta(),
    )
    stationkeeping_time: timedelta = pydantic.Field(
        serialization_alias="stationkeeping_time_minutes",
        validation_alias="stationkeeping_time_minutes",
        gt=timedelta(),
    )

    sensors: list[SensorConfig] = pydantic.Field(
        default_factory=lambda: [SensorConfig(sensor_type=SensorType.TEMPERATURE)],
        description=("Sensors fitted to the drifter. Supported: TEMPERATURE. "),
    )

    model_config = pydantic.ConfigDict(populate_by_name=True)


@register_instrument_config(InstrumentType.XBT)
class XBTConfig(_InstrumentConfigMixin, pydantic.BaseModel):
    """Configuration for xbt instrument."""

    _instrument_type: ClassVar[InstrumentType] = InstrumentType.XBT
    _instrument_name: ClassVar[str] = "XBT"

    min_depth_meter: float = pydantic.Field(le=0.0)
    max_depth_meter: float = pydantic.Field(le=0.0)
    fall_speed_meter_per_second: float = pydantic.Field(gt=0.0)
    deceleration_coefficient: float = pydantic.Field(gt=0.0)

    sensors: list[SensorConfig] = pydantic.Field(
        default_factory=lambda: [SensorConfig(sensor_type=SensorType.TEMPERATURE)],
        description=("Sensors fitted to the XBT. Supported: TEMPERATURE. "),
    )


class InstrumentsConfig(pydantic.BaseModel):
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


class SensorConfig(pydantic.BaseModel):
    """Configuration for a single sensor fitted to an instrument."""

    sensor_type: SensorType
    enabled: bool = True

    # validator/serialiser for allowing the compact, single-string notation for sensors in YAML (e.g. "TEMPERATURE" instead of sensor_type: TEMPERATURE in each instance
    @pydantic.model_validator(mode="before")
    @classmethod
    def _from_string(cls, value):
        """Allow a bare sensor-type string (e.g. "TEMPERATURE") as shorthand for {"sensor_type": "TEMPERATURE"}."""
        if isinstance(value, str):
            return {"sensor_type": value}
        return value

    @pydantic.field_validator("sensor_type", mode="before")
    @classmethod
    def _take_sensor_type(cls, value: str | SensorType) -> SensorType:
        """Accept a sensor-type string or SensorType class."""
        if isinstance(value, SensorType):
            return value
        return SensorType(value)

    @property
    def meta(self) -> _Sensor:
        """Metadata for this sensor."""
        return SENSOR_REGISTRY()[self.sensor_type]

    @staticmethod
    def serialize_list(sensors: list[SensorConfig]) -> list[str]:
        """Serialise enabled sensors to a list of sensor-type strings."""
        return [sc.sensor_type.value for sc in sensors if sc.enabled]

    @staticmethod
    def check_compatibility(
        sensors: list[SensorConfig],
        instrument_type: InstrumentType,
        instrument_name: str,
    ) -> list[SensorConfig]:
        """Error if any sensor is unsupported for the given instrument, or none are enabled."""
        supported = get_supported_sensors(instrument_type)
        unsupported = {sc.sensor_type for sc in sensors} - supported
        if unsupported:
            names = ", ".join(sorted(s.value for s in unsupported))
            valid = ", ".join(sorted(s.value for s in supported))
            raise ValueError(
                f"{instrument_name} does not support sensor(s): {names}. "
                f"Supported sensors: {valid}."
            )
        if not any(sc.enabled for sc in sensors):
            raise ValueError(
                f"{instrument_name} has no enabled sensors. "
                f"At least one sensor must be enabled."
            )
        return sensors

    @staticmethod
    def build_variables(sensors: list[SensorConfig]) -> dict[str, str]:
        """Build a FieldSet-key → Copernicus-variable mapping for enabled sensors."""
        return {sc.meta.fs_key: sc.meta.copernicus_var for sc in sensors if sc.enabled}
