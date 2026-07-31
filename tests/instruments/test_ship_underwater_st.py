"""Test the simulation of ship salinity temperature measurements."""

import datetime
from typing import ClassVar

import numpy as np
import parcels
import pydantic
import pytest
import xarray as xr

from virtualship.instruments.sensors import SensorType
from virtualship.instruments.ship_underwater_st import Underwater_STInstrument
from virtualship.instruments.types import InstrumentType
from virtualship.models import Location, Spacetime
from virtualship.models.expedition import (
    InstrumentsConfig,
    SensorConfig,
    ShipUnderwaterSTConfig,
    Waypoint,
)

BASE_TIME = datetime.datetime.strptime(
    "1950-01-01", "%Y-%m-%d"
)  # arbitrary time offset for the dummy fieldset
PERIOD = 5.0  # minutes


@pytest.fixture
def underwater_st_expedition():
    """Minimal Expedition for Underwater_STInstrument instantiation."""

    class DummyExpedition:
        class schedule:
            waypoints: ClassVar[list] = [
                Waypoint(
                    location=Location(1, 2),
                    time=BASE_TIME,
                    instrument=InstrumentType.UNDERWATER_ST,
                ),
            ]

        instruments_config = InstrumentsConfig(
            ship_underwater_st_config=ShipUnderwaterSTConfig(
                period_minutes=PERIOD,
                sensors=[
                    SensorConfig(sensor_type=SensorType.TEMPERATURE),
                    SensorConfig(sensor_type=SensorType.SALINITY),
                ],
            )
        )

    return DummyExpedition()


def test_simulate_ship_underwater_st(tmpdir, underwater_st_expedition) -> None:
    # where to sample
    sample_points = [
        Spacetime(Location(1, 2), BASE_TIME + datetime.timedelta(seconds=0)),
        Spacetime(Location(3, 4), BASE_TIME + datetime.timedelta(seconds=1)),
    ]

    # expected observations at sample points
    expected_obs = [
        {
            "S": 5,
            "T": 6,
            "lat": sample_points[0].location.lat,
            "lon": sample_points[0].location.lon,
            "time": BASE_TIME + datetime.timedelta(seconds=0),
        },
        {
            "S": 7,
            "T": 8,
            "lat": sample_points[1].location.lat,
            "lon": sample_points[1].location.lon,
            "time": BASE_TIME + datetime.timedelta(seconds=1),
        },
    ]

    # create fieldset based on the expected observations
    # indices are time, latitude, longitude
    salinity = np.zeros((2, 2, 2))
    salinity[0, 0, 0] = expected_obs[0]["S"]
    salinity[1, 1, 1] = expected_obs[1]["S"]

    temperature = np.zeros((2, 2, 2))
    temperature[0, 0, 0] = expected_obs[0]["T"]
    temperature[1, 1, 1] = expected_obs[1]["T"]

    # make ds
    times = np.array([expected_obs[0]["time"], expected_obs[1]["time"]])
    lats = np.array([expected_obs[0]["lat"], expected_obs[1]["lat"]])
    lons = np.array([expected_obs[0]["lon"], expected_obs[1]["lon"]])

    ds_fields = xr.Dataset(
        data_vars={
            "T": (["time", "lat", "lon"], temperature, {"units": "degC"}),
            "S": (["time", "lat", "lon"], salinity, {"units": "psu"}),
        },
        coords={
            "time": ("time", times, {"axis": "T"}),
            "lat": ("lat", lats, {"units": "degrees_north"}),
            "lon": ("lon", lons, {"units": "degrees_east"}),
        },
    )

    # to fieldset
    fields = {"T": ds_fields["T"], "S": ds_fields["S"]}
    ds_fset = parcels.convert.copernicusmarine_to_sgrid(fields=fields)
    fieldset = parcels.FieldSet.from_sgrid_conventions(ds_fset)

    st_instrument = Underwater_STInstrument(underwater_st_expedition, from_data=None)
    out_path = tmpdir.join("out.parquet")

    st_instrument.load_input_data = lambda: fieldset
    st_instrument.simulate(sample_points, out_path)

    results = parcels.read_particlefile(out_path)

    # expect a single depth level
    assert np.unique(results["z"].to_numpy()).size == 1

    # expect as many obs as sample points (given the period is 5 minutes and the sample points are 1 second apart)
    assert len(results) == len(sample_points)

    # for every obs, check if the variables match the expected observations
    for i, (obs_i, exp) in enumerate(
        zip(results.iter_rows(named=True), expected_obs, strict=True)
    ):
        for var in [("y", "lat"), ("x", "lon")]:
            obs_value = obs_i[var[0]]
            exp_value = exp[var[1]]
            assert np.isclose(obs_value, exp_value), (
                f"Observation incorrect {obs_i=} {var=} {obs_value=} {exp_value=}."
            )
        for var in ["T", "S"]:
            obs_value = obs_i[var]
            exp_value = exp[var]
            assert np.isclose(obs_value, exp_value), (
                f"Observation incorrect {i=} {var=} {obs_value=} {exp_value=}."
            )


def test_ship_underwater_st_sensor_config_active_variables() -> None:
    """active_variables() only returns variables for enabled sensors."""
    config_both = ShipUnderwaterSTConfig(
        period_minutes=5.0,
        sensors=[
            SensorConfig(sensor_type=SensorType.TEMPERATURE),
            SensorConfig(sensor_type=SensorType.SALINITY),
        ],
    )
    assert config_both.active_variables() == {"T": "thetao", "S": "so"}

    config_temp_only = ShipUnderwaterSTConfig(
        period_minutes=5.0,
        sensors=[
            SensorConfig(sensor_type=SensorType.TEMPERATURE)
        ],  # SALINITY omitted = disabled
    )
    assert config_temp_only.active_variables() == {"T": "thetao"}


def test_ship_underwater_st_sensor_config_yaml() -> None:
    """ShipUnderwaterSTConfig sensors survive YAML serialisation."""
    config = ShipUnderwaterSTConfig(
        period_minutes=5.0,
        sensors=[
            SensorConfig(sensor_type=SensorType.TEMPERATURE)
        ],  # SALINITY omitted = disabled
    )
    dumped = config.model_dump(by_alias=True)
    loaded = ShipUnderwaterSTConfig.model_validate(dumped)
    assert len(loaded.sensors) == 1
    assert loaded.sensors[0].sensor_type == SensorType.TEMPERATURE
    assert loaded.sensors[0].enabled is True


def test_underwater_st_config_default_sensors():
    """ShipUnderwaterSTConfig defaults to TEMPERATURE + SALINITY."""
    config = ShipUnderwaterSTConfig(
        period_minutes=5.0,
    )
    types = {sc.sensor_type for sc in config.sensors}
    assert types == {SensorType.TEMPERATURE, SensorType.SALINITY}


def test_underwater_st_config_unsupported_sensor_rejected():
    """Unsupported sensor on Underwater ST is rejected."""
    with pytest.raises(pydantic.ValidationError, match="does not support"):
        ShipUnderwaterSTConfig(
            period_minutes=5.0,
            sensors=[SensorConfig(sensor_type=SensorType.OXYGEN)],
        )


def test_underwater_st_instrument_type(underwater_st_expedition):
    """Underwater_STInstrument returns the correct InstrumentType and if is underway instrument."""
    underwater_st_instrument = Underwater_STInstrument(
        underwater_st_expedition, from_data=None
    )
    assert underwater_st_instrument.instrument_type == InstrumentType.UNDERWATER_ST
    assert underwater_st_instrument.instrument_type.is_underway
