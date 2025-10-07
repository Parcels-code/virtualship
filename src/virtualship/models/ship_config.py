"""ShipConfig and supporting classes."""

from __future__ import annotations

from datetime import timedelta
from pathlib import Path
from typing import TYPE_CHECKING

import pydantic
import yaml

from virtualship.errors import ConfigError
from virtualship.instruments.master import InstrumentType
from virtualship.utils import _validate_numeric_mins_to_timedelta

if TYPE_CHECKING:
    from .schedule import Schedule


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


class ShipConfig(pydantic.BaseModel):
    """Configuration of the virtual ship."""

    ship_speed_knots: float = pydantic.Field(gt=0.0)
    """
    Velocity of the ship in knots.
    """

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

    def to_yaml(self, file_path: str | Path) -> None:
        """
        Write config to yaml file.

        :param file_path: Path to the file to write to.
        """
        with open(file_path, "w") as file:
            yaml.dump(self.model_dump(by_alias=True), file)

    @classmethod
    def from_yaml(cls, file_path: str | Path) -> ShipConfig:
        """
        Load config from yaml file.

        :param file_path: Path to the file to load from.
        :returns: The config.
        """
        with open(file_path) as file:
            data = yaml.safe_load(file)
        return ShipConfig(**data)

    def verify(self, schedule: Schedule) -> None:
        """
        Verify the ship configuration against the provided schedule.

        This function performs two main tasks:
        1. Removes instrument configurations that are not present in the schedule.
        2. Verifies that all instruments in the schedule have corresponding configurations.

        Parameters
        ----------
        schedule : Schedule
            The schedule object containing the planned instruments and waypoints.

        Returns
        -------
        None

        Raises
        ------
        ConfigError
            If an instrument in the schedule does not have a corresponding configuration.

        Notes
        -----
        - Prints a message if a configuration is provided for an instrument not in the schedule.
        - Sets the configuration to None for instruments not in the schedule.
        - Raises a ConfigError for each instrument in the schedule that lacks a configuration.

        """
        instruments_in_schedule = schedule.get_instruments()

        for instrument in [
            "ARGO_FLOAT",
            "DRIFTER",
            "XBT",
            "CTD",
            "CTD_BGC",
        ]:  # TODO make instrument names consistent capitals or lowercase throughout codebase
            if hasattr(self, instrument.lower() + "_config") and not any(
                instrument == schedule_instrument.name
                for schedule_instrument in instruments_in_schedule
            ):
                print(f"{instrument} configuration provided but not in schedule.")
                setattr(self, instrument.lower() + "_config", None)

        # verify instruments in schedule have configuration
        # TODO: the ConfigError message could be improved to explain that the **schedule** file has X instrument but the **ship_config** file does not
        for instrument in instruments_in_schedule:
            try:
                InstrumentType(instrument)
            except ValueError as e:
                raise NotImplementedError("Instrument not supported.") from e

            if instrument == InstrumentType.ARGO_FLOAT and (
                not hasattr(self, "argo_float_config") or self.argo_float_config is None
            ):
                raise ConfigError(
                    "Planning has a waypoint with Argo float instrument, but configuration does not configure Argo floats."
                )
            if instrument == InstrumentType.CTD and (
                not hasattr(self, "ctd_config") or self.ctd_config is None
            ):
                raise ConfigError(
                    "Planning has a waypoint with CTD instrument, but configuration does not configure CTDs."
                )
            if instrument == InstrumentType.CTD_BGC and (
                not hasattr(self, "ctd_bgc_config") or self.ctd_bgc_config is None
            ):
                raise ConfigError(
                    "Planning has a waypoint with CTD_BGC instrument, but configuration does not configure CTD_BGCs."
                )
            if instrument == InstrumentType.DRIFTER and (
                not hasattr(self, "drifter_config") or self.drifter_config is None
            ):
                raise ConfigError(
                    "Planning has a waypoint with drifter instrument, but configuration does not configure drifters."
                )

            if instrument == InstrumentType.XBT and (
                not hasattr(self, "xbt_config") or self.xbt_config is None
            ):
                raise ConfigError(
                    "Planning has a waypoint with XBT instrument, but configuration does not configure XBT."
                )
