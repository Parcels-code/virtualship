"""
Test the simulation of XBT instruments.

Fields are kept static over time and time component of XBT measurements is not tested tested because it's tricky to provide expected measurements.
"""

import datetime
from typing import ClassVar

import numpy as np
import pydantic
import pytest
import xarray as xr
from parcels import Field, FieldSet

from virtualship.instruments.sensors import SensorType
from virtualship.instruments.types import InstrumentType
from virtualship.instruments.xbt import XBT, XBTInstrument
from virtualship.models import Location, Spacetime
from virtualship.models.expedition import (
    InstrumentsConfig,
    SensorConfig,
    Waypoint,
    XBTConfig,
)

BASE_TIME = datetime.datetime.strptime(
    "1950-01-01", "%Y-%m-%d"
)  # arbitrary time offset for the dummy fieldset
MIN_DEPTH = -2.0
MAX_DEPTH = -285.0
FALL_SPEED = 6.7
DECELERATION_COEFFICIENT = 0.00225


@pytest.fixture
def xbt_expedition():
    """Minimal Expedition for Underwater_STInstrument instantiation."""

    class DummyExpedition:
        class schedule:
            waypoints: ClassVar[list] = [
                Waypoint(
                    location=Location(1, 2),
                    time=BASE_TIME,
                    instrument=InstrumentType.XBT,
                ),
            ]

        instruments_config = InstrumentsConfig(
            xbt_config=XBTConfig(
                min_depth_meter=MIN_DEPTH,
                max_depth_meter=MAX_DEPTH,
                fall_speed_meter_per_second=FALL_SPEED,
                deceleration_coefficient=DECELERATION_COEFFICIENT,
                sensors=[SensorConfig(sensor_type=SensorType.TEMPERATURE)],
            )
        )

    return DummyExpedition()


def test_simulate_xbts(tmpdir, xbt_expedition) -> None:
    # arbitrary time offset for the dummy fieldset
    base_time = datetime.datetime.strptime("1950-01-01", "%Y-%m-%d")

    # where to cast XBTs
    xbts = [
        XBT(
            spacetime=Spacetime(
                location=Location(latitude=0, longitude=1),
                time=base_time + datetime.timedelta(hours=0),
            ),
            min_depth=0,
            max_depth=float("-inf"),
            fall_speed=6.553,
            deceleration_coefficient=0.00242,
        ),
        XBT(
            spacetime=Spacetime(
                location=Location(latitude=1, longitude=0),
                time=base_time,
            ),
            min_depth=0,
            max_depth=float("-inf"),
            fall_speed=6.553,
            deceleration_coefficient=0.00242,
        ),
    ]

    # expected observations for xbts at surface and at maximum depth
    xbt_exp = [
        {
            "surface": {
                "temperature": 6,
                "lat": xbts[0].spacetime.location.lat,
                "lon": xbts[0].spacetime.location.lon,
            },
            "maxdepth": {
                "temperature": 8,
                "lat": xbts[0].spacetime.location.lat,
                "lon": xbts[0].spacetime.location.lon,
            },
        },
        {
            "surface": {
                "temperature": 6,
                "lat": xbts[1].spacetime.location.lat,
                "lon": xbts[1].spacetime.location.lon,
            },
            "maxdepth": {
                "temperature": 8,
                "lat": xbts[1].spacetime.location.lat,
                "lon": xbts[1].spacetime.location.lon,
            },
        },
    ]

    # create fieldset based on the expected observations
    # indices are time, depth, latitude, longitude
    u = np.zeros((2, 2, 2, 2))
    v = np.zeros((2, 2, 2, 2))
    t = np.zeros((2, 2, 2, 2))

    t[:, 1, 0, 1] = xbt_exp[0]["surface"]["temperature"]
    t[:, 0, 0, 1] = xbt_exp[0]["maxdepth"]["temperature"]
    t[:, 1, 1, 0] = xbt_exp[1]["surface"]["temperature"]
    t[:, 0, 1, 0] = xbt_exp[1]["maxdepth"]["temperature"]

    fieldset = FieldSet.from_data(
        {"V": v, "U": u, "T": t},
        {
            "time": [
                np.datetime64(base_time + datetime.timedelta(hours=0)),
                np.datetime64(base_time + datetime.timedelta(hours=1)),
            ],
            "depth": [-1000, 0],
            "lat": [0, 1],
            "lon": [0, 1],
        },
    )
    fieldset.add_field(Field("bathymetry", [-1000], lon=0, lat=0))

    from_data = None

    xbt_instrument = XBTInstrument(xbt_expedition, from_data)
    out_path = tmpdir.join("out.zarr")

    xbt_instrument.load_input_data = lambda: fieldset
    xbt_instrument.simulate(xbts, out_path)

    # test if output is as expected
    results = xr.open_zarr(out_path)

    assert len(results.trajectory) == len(xbts)

    for xbt_i, (traj, exp_bothloc) in enumerate(
        zip(results.trajectory, xbt_exp, strict=True)
    ):
        obs_surface = results.sel(trajectory=traj, obs=0)
        min_index = np.argmin(results.sel(trajectory=traj)["z"].data)
        obs_maxdepth = results.sel(trajectory=traj, obs=min_index)

        for obs, loc in [
            (obs_surface, "surface"),
            (obs_maxdepth, "maxdepth"),
        ]:
            exp = exp_bothloc[loc]
            for var in ["temperature", "lat", "lon"]:
                obs_value = obs[var].values.item()
                exp_value = exp[var]
                assert np.isclose(obs_value, exp_value), (
                    f"Observation incorrect {xbt_i=} {loc=} {var=} {obs_value=} {exp_value=}."
                )


def test_xbt_sensor_config_active_variables() -> None:
    """active_variables() only returns variables for enabled sensors."""
    config_with_temp = XBTConfig(
        min_depth_meter=-2.0,
        max_depth_meter=-285.0,
        fall_speed_meter_per_second=6.7,
        deceleration_coefficient=0.00225,
        sensors=[SensorConfig(sensor_type=SensorType.TEMPERATURE)],
    )
    assert config_with_temp.active_variables() == {"T": "thetao"}


def test_xbt_sensor_config_yaml() -> None:
    """XBTConfig sensors survive YAML serialisation."""
    config = XBTConfig(
        min_depth_meter=-2.0,
        max_depth_meter=-285.0,
        fall_speed_meter_per_second=6.7,
        deceleration_coefficient=0.00225,
        sensors=[SensorConfig(sensor_type=SensorType.TEMPERATURE)],
    )
    dumped = config.model_dump(by_alias=True)
    loaded = XBTConfig.model_validate(dumped)
    assert len(loaded.sensors) == 1
    assert loaded.sensors[0].sensor_type == SensorType.TEMPERATURE
    assert loaded.sensors[0].enabled is True


def test_xbt_config_default_sensors():
    """XBTConfig defaults to TEMPERATURE."""
    config = XBTConfig(
        min_depth_meter=-2.0,
        max_depth_meter=-285.0,
        fall_speed_meter_per_second=6.7,
        deceleration_coefficient=0.00225,
    )
    assert config.sensors[0].sensor_type is SensorType.TEMPERATURE


def test_xbt_config_unsupported_sensor_rejected():
    """Unsupported sensor on XBT is rejected."""
    with pytest.raises(pydantic.ValidationError, match="does not support"):
        XBTConfig(
            min_depth_meter=-2.0,
            max_depth_meter=-285.0,
            fall_speed_meter_per_second=6.7,
            deceleration_coefficient=0.00225,
            sensors=[SensorConfig(sensor_type=SensorType.SALINITY)],
        )


def test_xbt_instrument_type(xbt_expedition):
    """XBTInstrument returns the correct InstrumentType and if is underway instrument."""
    xbt_instrument = XBTInstrument(xbt_expedition, from_data=None)
    assert xbt_instrument.instrument_type == InstrumentType.XBT
    assert not xbt_instrument.instrument_type.is_underway
