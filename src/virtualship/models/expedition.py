from __future__ import annotations

import itertools
from datetime import datetime, timedelta
from pathlib import Path

import numpy as np
import pydantic
import pyproj
import yaml

from virtualship.errors import InstrumentsConfigError, ScheduleError
from virtualship.instruments.sensors import (
    ADCP_SUPPORTED_SENSORS,
    ARGO_FLOAT_SUPPORTED_SENSORS,
    CTD_BGC_SUPPORTED_SENSORS,
    CTD_SUPPORTED_SENSORS,
    DRIFTER_SUPPORTED_SENSORS,
    UNDERWATER_ST_SUPPORTED_SENSORS,
    XBT_SUPPORTED_SENSORS,
    SensorType,
)
from virtualship.instruments.types import InstrumentType
from virtualship.utils import (
    SENSOR_REGISTRY,
    _calc_sail_time,
    _calc_wp_stationkeeping_time,
    _get_bathy_data,
    _get_waypoint_latlons,
    _SensorMeta,
    _validate_numeric_to_timedelta,
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


def _serialize_sensor_list(sensors: list[SensorConfig]) -> list[str]:
    """Serialise enabled sensors to a compact list of sensor-type name strings."""
    return [sc.sensor_type.value for sc in sensors if sc.enabled]


def _check_sensor_compatibility(
    sensors: list[SensorConfig],
    supported: frozenset[SensorType],
    instrument_name: str,
) -> list[SensorConfig]:
    """Raise ValueError if any sensor in `sensors` is not in `supported`, or if no sensors are enabled. Used as a Pydantic field_validator for each instrument config class."""
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


def build_variables_from_sensors(sensors: list[SensorConfig]) -> dict[str, str]:
    """Build variables dict (FieldSet key → Copernicus-variable)."""
    return {sc.meta.fs_key: sc.meta.copernicus_var for sc in sensors if sc.enabled}


@register_instrument_config(InstrumentType.ARGO_FLOAT)
class ArgoFloatConfig(pydantic.BaseModel):
    """Configuration for argos floats."""

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

    @pydantic.field_serializer("lifetime")
    def _serialize_lifetime(self, value: timedelta, _info):
        return value.total_seconds() / 86400.0  # [days]

    @pydantic.field_validator("lifetime", mode="before")
    def _validate_lifetime(cls, value: int | float | timedelta) -> timedelta:
        return _validate_numeric_to_timedelta(value, "days")

    @pydantic.field_serializer("stationkeeping_time")
    def _serialize_stationkeeping_time(self, value: timedelta, _info):
        return value.total_seconds() / 60.0

    @pydantic.field_validator("stationkeeping_time", mode="before")
    def _validate_stationkeeping_time(cls, value: int | float | timedelta) -> timedelta:
        return _validate_numeric_to_timedelta(value, "minutes")

    @pydantic.field_validator("sensors", mode="after")
    @classmethod
    def _check_sensor_compatibility(cls, value) -> list[SensorConfig]:
        return _check_sensor_compatibility(
            value, ARGO_FLOAT_SUPPORTED_SENSORS, "ArgoFloat"
        )

    @pydantic.field_serializer("sensors")
    def _serialize_sensors(self, value: list[SensorConfig], _info):
        return _serialize_sensor_list(value)

    model_config = pydantic.ConfigDict(populate_by_name=True)

    def active_variables(self) -> dict[str, str]:
        """FieldSet-key → Copernicus-variable mapping for enabled sensors."""
        return build_variables_from_sensors(self.sensors)


@register_instrument_config(InstrumentType.ADCP)
class ADCPConfig(pydantic.BaseModel):
    """Configuration for ADCP instrument."""

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

    @pydantic.field_serializer("period")
    def _serialize_period(self, value: timedelta, _info):
        return value.total_seconds() / 60.0

    @pydantic.field_validator("period", mode="before")
    def _validate_period(cls, value: int | float | timedelta) -> timedelta:
        return _validate_numeric_to_timedelta(value, "minutes")

    @pydantic.field_validator("sensors", mode="after")
    @classmethod
    def _check_sensor_compatibility(cls, value) -> list[SensorConfig]:
        return _check_sensor_compatibility(value, ADCP_SUPPORTED_SENSORS, "ADCP")

    @pydantic.field_serializer("sensors")
    def _serialize_sensors(self, value: list[SensorConfig], _info):
        return _serialize_sensor_list(value)

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
class CTDConfig(pydantic.BaseModel):
    """Configuration for CTD instrument."""

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

    @pydantic.field_serializer("stationkeeping_time")
    def _serialize_stationkeeping_time(self, value: timedelta, _info):
        return value.total_seconds() / 60.0

    @pydantic.field_validator("stationkeeping_time", mode="before")
    def _validate_stationkeeping_time(cls, value: int | float | timedelta) -> timedelta:
        return _validate_numeric_to_timedelta(value, "minutes")

    @pydantic.field_validator("sensors", mode="after")
    @classmethod
    def _check_sensor_compatibility(cls, value) -> list[SensorConfig]:
        return _check_sensor_compatibility(value, CTD_SUPPORTED_SENSORS, "CTD")

    @pydantic.field_serializer("sensors")
    def _serialize_sensors(self, value: list[SensorConfig], _info):
        return _serialize_sensor_list(value)

    def active_variables(self) -> dict[str, str]:
        """FieldSet-key → Copernicus-variable mapping for enabled sensors."""
        return build_variables_from_sensors(self.sensors)


@register_instrument_config(InstrumentType.CTD_BGC)
class CTD_BGCConfig(pydantic.BaseModel):
    """Configuration for CTD_BGC instrument."""

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
            "Supported: CHLOROPHYLL, NITRATE, OXYGEN, PH, PHOSPHATE, PHYTOPLANKTON, PRIMARY_PRODUCTION. "
        ),
    )

    model_config = pydantic.ConfigDict(populate_by_name=True)

    @pydantic.field_serializer("stationkeeping_time")
    def _serialize_stationkeeping_time(self, value: timedelta, _info):
        return value.total_seconds() / 60.0

    @pydantic.field_validator("stationkeeping_time", mode="before")
    def _validate_stationkeeping_time(cls, value: int | float | timedelta) -> timedelta:
        return _validate_numeric_to_timedelta(value, "minutes")

    @pydantic.field_validator("sensors", mode="after")
    @classmethod
    def _check_sensor_compatibility(cls, value) -> list[SensorConfig]:
        return _check_sensor_compatibility(value, CTD_BGC_SUPPORTED_SENSORS, "CTD_BGC")

    @pydantic.field_serializer("sensors")
    def _serialize_sensors(self, value: list[SensorConfig], _info):
        return _serialize_sensor_list(value)

    def active_variables(self) -> dict[str, str]:
        """FieldSet-key → Copernicus-variable mapping for enabled sensors."""
        return build_variables_from_sensors(self.sensors)


@register_instrument_config(InstrumentType.UNDERWATER_ST)
class ShipUnderwaterSTConfig(pydantic.BaseModel):
    """Configuration for underwater ST."""

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

    @pydantic.field_serializer("period")
    def _serialize_period(self, value: timedelta, _info):
        return value.total_seconds() / 60.0

    @pydantic.field_validator("period", mode="before")
    def _validate_period(cls, value: int | float | timedelta) -> timedelta:
        return _validate_numeric_to_timedelta(value, "minutes")

    @pydantic.field_validator("sensors", mode="after")
    @classmethod
    def _check_sensor_compatibility(cls, value) -> list[SensorConfig]:
        return _check_sensor_compatibility(
            value, UNDERWATER_ST_SUPPORTED_SENSORS, "Underwater ST"
        )

    @pydantic.field_serializer("sensors")
    def _serialize_sensors(self, value: list[SensorConfig], _info):
        return _serialize_sensor_list(value)

    def active_variables(self) -> dict[str, str]:
        """FieldSet-key → Copernicus-variable mapping for enabled sensors."""
        return build_variables_from_sensors(self.sensors)


@register_instrument_config(InstrumentType.DRIFTER)
class DrifterConfig(pydantic.BaseModel):
    """Configuration for drifters."""

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

    @pydantic.field_serializer("lifetime")
    def _serialize_lifetime(self, value: timedelta, _info):
        return value.total_seconds() / 86400.0  # [days]

    @pydantic.field_validator("lifetime", mode="before")
    def _validate_lifetime(cls, value: int | float | timedelta) -> timedelta:
        return _validate_numeric_to_timedelta(value, "days")

    @pydantic.field_serializer("stationkeeping_time")
    def _serialize_stationkeeping_time(self, value: timedelta, _info):
        return value.total_seconds() / 60.0

    @pydantic.field_validator("stationkeeping_time", mode="before")
    def _validate_stationkeeping_time(cls, value: int | float | timedelta) -> timedelta:
        return _validate_numeric_to_timedelta(value, "minutes")

    @pydantic.field_validator("sensors", mode="after")
    @classmethod
    def _check_sensor_compatibility(cls, value) -> list[SensorConfig]:
        return _check_sensor_compatibility(value, DRIFTER_SUPPORTED_SENSORS, "Drifter")

    @pydantic.field_serializer("sensors")
    def _serialize_sensors(self, value: list[SensorConfig], _info):
        return _serialize_sensor_list(value)

    def active_variables(self) -> dict[str, str]:
        """FieldSet-key → Copernicus-variable mapping for enabled sensors."""
        return build_variables_from_sensors(self.sensors)


@register_instrument_config(InstrumentType.XBT)
class XBTConfig(pydantic.BaseModel):
    """Configuration for xbt instrument."""

    min_depth_meter: float = pydantic.Field(le=0.0)
    max_depth_meter: float = pydantic.Field(le=0.0)
    fall_speed_meter_per_second: float = pydantic.Field(gt=0.0)
    deceleration_coefficient: float = pydantic.Field(gt=0.0)

    sensors: list[SensorConfig] = pydantic.Field(
        default_factory=lambda: [SensorConfig(sensor_type=SensorType.TEMPERATURE)],
        description=("Sensors fitted to the XBT. Supported: TEMPERATURE. "),
    )

    @pydantic.field_validator("sensors", mode="after")
    @classmethod
    def _check_sensor_compatibility(cls, value) -> list[SensorConfig]:
        return _check_sensor_compatibility(value, XBT_SUPPORTED_SENSORS, "XBT")

    @pydantic.field_serializer("sensors")
    def _serialize_sensors(self, value: list[SensorConfig], _info):
        return _serialize_sensor_list(value)

    def active_variables(self) -> dict[str, str]:
        """FieldSet-key → Copernicus-variable mapping for enabled sensors."""
        return build_variables_from_sensors(self.sensors)


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
    def meta(self) -> _SensorMeta:
        """Metadata for this sensor."""
        return SENSOR_REGISTRY()[self.sensor_type]
