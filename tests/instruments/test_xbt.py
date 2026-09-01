"""
Test the simulation of XBT instruments.

Fields are kept static over time and time component of XBT measurements is not tested tested because it's tricky to provide expected measurements.
"""

import datetime
from typing import ClassVar

import numpy as np
import parcels
import polars as pl
import pydantic
import pytest
import xarray as xr

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


def create_fieldset(
    data_dict,
    lon_range=(0.0, 1.0),
    lat_range=(0.0, 1.0),
    depth_range=(-1000, 0),
    time_range=None,
    bathymetry_val=-1000.0,
):
    if time_range is None:
        time_range = [
            np.datetime64(BASE_TIME),
            np.datetime64(BASE_TIME + datetime.timedelta(hours=3)),
        ]
    data_vars = {}
    for key, val in data_dict.items():
        data_vars[key] = (("time", "depth", "lat", "lon"), val)

    ds_fields = xr.Dataset(
        data_vars=data_vars,
        coords={
            "lon": (("lon"), np.array(lon_range), {"units": "degrees_east"}),
            "lat": (("lat"), np.array(lat_range), {"units": "degrees_north"}),
            "depth": (("depth"), np.array(depth_range)),
            "time": (
                ("time"),
                time_range,
                {"axis": "T"},
            ),
        },
    )

    fields = {var: ds_fields[var] for var in data_vars.keys()}
    ds_fset = parcels.convert.copernicusmarine_to_sgrid(fields=fields)
    fieldset = parcels.FieldSet.from_sgrid_conventions(ds_fset)

    ds_bathymetry = xr.Dataset(
        data_vars={
            "bathymetry": (
                ("lat", "lon"),
                np.full((len(lat_range), len(lon_range)), bathymetry_val),
            )
        },
        coords={
            "lon": (("lon"), np.array(lon_range), {"units": "degrees_east"}),
            "lat": (("lat"), np.array(lat_range), {"units": "degrees_north"}),
        },
    )
    ds_bathymetry_fset = parcels.convert.copernicusmarine_to_sgrid(
        fields={"bathymetry": ds_bathymetry["bathymetry"]}
    )
    bathymetry_fset = parcels.FieldSet.from_sgrid_conventions(ds_bathymetry_fset)

    return fieldset + bathymetry_fset


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
            fall_speed=FALL_SPEED,
            deceleration_coefficient=DECELERATION_COEFFICIENT,
        ),
        XBT(
            spacetime=Spacetime(
                location=Location(latitude=1, longitude=0),
                time=base_time + datetime.timedelta(hours=1),
            ),
            min_depth=0,
            max_depth=float("-inf"),
            fall_speed=FALL_SPEED,
            deceleration_coefficient=DECELERATION_COEFFICIENT,
        ),
    ]

    # expected observations for xbts at surface and at maximum depth
    xbt_exp = [
        {
            "surface": {
                "temperature": 6,
                "y": xbts[0].spacetime.location.lat,
                "x": xbts[0].spacetime.location.lon,
            },
            "maxdepth": {
                "temperature": 8,
                "y": xbts[0].spacetime.location.lat,
                "x": xbts[0].spacetime.location.lon,
            },
        },
        {
            "surface": {
                "temperature": 6,
                "y": xbts[1].spacetime.location.lat,
                "x": xbts[1].spacetime.location.lon,
            },
            "maxdepth": {
                "temperature": 8,
                "y": xbts[1].spacetime.location.lat,
                "x": xbts[1].spacetime.location.lon,
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

    fieldset = create_fieldset({"V": v, "U": u, "T": t})

    from_data = None

    xbt_instrument = XBTInstrument(xbt_expedition, from_data)
    out_path = tmpdir.join("out.parquet")

    xbt_instrument.load_input_data = lambda: fieldset
    xbt_instrument.simulate(xbts, out_path)

    # test if output is as expected
    results = parcels.read_particlefile(out_path)

    assert np.unique(results["particle_id"].to_numpy()).size == len(xbts)

    for xbt_i, id in enumerate(np.unique(results["particle_id"].to_numpy())):
        xbt_df = results.filter(pl.col("particle_id") == id)
        obs_surface = xbt_df.filter(pl.col("z") == xbt_df["z"].max())[0]
        obs_maxdepth = xbt_df.filter(pl.col("z") == xbt_df["z"].min())[0]

        for obs, loc in [
            (obs_surface, "surface"),
            (obs_maxdepth, "maxdepth"),
        ]:
            exp = xbt_exp[xbt_i][loc]
            for var in ["temperature", "y", "x"]:
                obs_value = obs[var].item()
                exp_value = exp[var]
                assert np.isclose(obs_value, exp_value, rtol=0.1), (
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
