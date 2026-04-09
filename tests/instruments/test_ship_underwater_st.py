"""Test the simulation of ship salinity temperature measurements."""

import datetime

import numpy as np
import pydantic
import pytest
import xarray as xr

from parcels import FieldSet
from virtualship.instruments.ship_underwater_st import Underwater_STInstrument
from virtualship.instruments.sensors import UNDERWATER_ST_SUPPORTED_SENSORS, SensorType
from virtualship.models import Location, Spacetime
from virtualship.models.expedition import (
    InstrumentsConfig,
    SensorConfig,
    ShipUnderwaterSTConfig,
    Waypoint,
)


def test_simulate_ship_underwater_st(tmpdir) -> None:
    # arbitrary time offset for the dummy fieldset
    base_time = datetime.datetime.strptime("1950-01-01", "%Y-%m-%d")

    # where to sample
    sample_points = [
        Spacetime(Location(1, 2), base_time + datetime.timedelta(seconds=0)),
        Spacetime(Location(3, 4), base_time + datetime.timedelta(seconds=1)),
    ]

    # expected observations at sample points
    expected_obs = [
        {
            "salinity": 5,
            "temperature": 6,
            "lat": sample_points[0].location.lat,
            "lon": sample_points[0].location.lon,
            "time": base_time + datetime.timedelta(seconds=0),
        },
        {
            "salinity": 7,
            "temperature": 8,
            "lat": sample_points[1].location.lat,
            "lon": sample_points[1].location.lon,
            "time": base_time + datetime.timedelta(seconds=1),
        },
    ]

    # create fieldset based on the expected observations
    # indices are time, latitude, longitude
    salinity = np.zeros((2, 2, 2))
    salinity[0, 0, 0] = expected_obs[0]["salinity"]
    salinity[1, 1, 1] = expected_obs[1]["salinity"]

    temperature = np.zeros((2, 2, 2))
    temperature[0, 0, 0] = expected_obs[0]["temperature"]
    temperature[1, 1, 1] = expected_obs[1]["temperature"]

    fieldset = FieldSet.from_data(
        {
            "V": np.zeros((2, 2, 2)),
            "U": np.zeros((2, 2, 2)),
            "S": salinity,
            "T": temperature,
        },
        {
            "lat": np.array([expected_obs[0]["lat"], expected_obs[1]["lat"]]),
            "lon": np.array([expected_obs[0]["lon"], expected_obs[1]["lon"]]),
            "time": np.array(
                [
                    np.datetime64(expected_obs[0]["time"]),
                    np.datetime64(expected_obs[1]["time"]),
                ]
            ),
        },
    )

    # dummy expedition for Underwater_STInstrument
    class DummyExpedition:
        class schedule:
            # ruff: noqa
            waypoints = [
                Waypoint(
                    location=Location(1, 2),
                    time=base_time,
                ),
            ]

        instruments_config = InstrumentsConfig(
            ship_underwater_st_config=ShipUnderwaterSTConfig(
                period_minutes=5.0,
                sensors=[
                    SensorConfig(sensor_type=SensorType.TEMPERATURE),
                    SensorConfig(sensor_type=SensorType.SALINITY),
                ],
            )
        )

    expedition = DummyExpedition()
    from_data = None

    st_instrument = Underwater_STInstrument(expedition, from_data)
    out_path = tmpdir.join("out.zarr")

    st_instrument.load_input_data = lambda: fieldset
    # The instrument expects measurements as sample_points
    st_instrument.simulate(sample_points, out_path)

    # test if output is as expected
    results = xr.open_zarr(out_path)

    assert len(results.trajectory) == 1  # expect a single trajectory
    traj = results.trajectory.item()
    assert len(results.sel(trajectory=traj).obs) == len(
        sample_points
    )  # expect as many obs as sample points

    # for every obs, check if the variables match the expected observations
    for i, (obs_i, exp) in enumerate(
        zip(results.sel(trajectory=traj).obs, expected_obs, strict=True)
    ):
        obs = results.sel(trajectory=traj, obs=obs_i)
        for var in ["salinity", "temperature", "lat", "lon"]:
            obs_value = obs[var].values.item()
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

    with pytest.raises(pydantic.ValidationError, match="no enabled sensors"):
        ShipUnderwaterSTConfig(
            period_minutes=5.0,
            sensors=[],  # all disabled → invalid
        )


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


def test_underwater_st_supported_sensors():
    """Underwater ST supports TEMPERATURE and SALINITY."""
    assert UNDERWATER_ST_SUPPORTED_SENSORS == frozenset(
        {SensorType.TEMPERATURE, SensorType.SALINITY}
    )


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
