"""Test the simulation of ADCP instruments."""

import datetime
from typing import ClassVar

import numpy as np
import parcels
import polars as pl
import pydantic
import pytest
import xarray as xr

from virtualship.instruments.adcp import ADCPInstrument
from virtualship.instruments.sensors import SensorType
from virtualship.instruments.types import InstrumentType
from virtualship.models import Location, Spacetime, Waypoint
from virtualship.models.expedition import ADCPConfig, InstrumentsConfig, SensorConfig

# =====================================================
# Shared constants and fixtures
# =====================================================

BASE_TIME = datetime.datetime.strptime(
    "1950-01-01", "%Y-%m-%d"
)  # arbitrary time offset for the dummy fieldset
MIN_DEPTH = -5
MAX_DEPTH = -1000
NUM_BINS = 40


@pytest.fixture
def adcp_expedition():
    """Minimal Expedition for ADCPInstrument instantiation."""

    class DummyExpedition:
        class schedule:
            waypoints: ClassVar[list] = [
                Waypoint(
                    location=Location(1, 2),
                    time=BASE_TIME,
                    instrument=InstrumentType.ADCP,
                ),
            ]

        instruments_config = InstrumentsConfig(
            adcp_config=ADCPConfig(
                max_depth_meter=MAX_DEPTH,
                num_bins=NUM_BINS,
                period_minutes=5.0,
                sensors=[SensorConfig(sensor_type=SensorType.VELOCITY)],
            )
        )

    return DummyExpedition()


def test_simulate_adcp(tmpdir, adcp_expedition) -> None:
    # where to sample
    sample_points = [
        Spacetime(Location(1, 2), BASE_TIME + datetime.timedelta(seconds=0)),
        Spacetime(Location(3, 4), BASE_TIME + datetime.timedelta(seconds=1)),
    ]

    # expected observations at sample points
    expected_obs = [
        {
            "V": {"surface": 5, "max_depth": 6},
            "U": {"surface": 7, "max_depth": 8},
            "lat": sample_points[0].location.lat,
            "lon": sample_points[0].location.lon,
            "time": BASE_TIME + datetime.timedelta(seconds=0),
        },
        {
            "V": {"surface": 9, "max_depth": 10},
            "U": {"surface": 11, "max_depth": 12},
            "lat": sample_points[1].location.lat,
            "lon": sample_points[1].location.lon,
            "time": BASE_TIME + datetime.timedelta(seconds=1),
        },
    ]

    # create fieldset based on the expected observations
    # indices are time, depth, latitude, longitude
    v = np.zeros((2, 2, 2, 2))
    v[0, 0, 0, 0] = expected_obs[0]["V"]["max_depth"]
    v[0, 1, 0, 0] = expected_obs[0]["V"]["surface"]
    v[1, 0, 1, 1] = expected_obs[1]["V"]["max_depth"]
    v[1, 1, 1, 1] = expected_obs[1]["V"]["surface"]

    u = np.zeros((2, 2, 2, 2))
    u[0, 0, 0, 0] = expected_obs[0]["U"]["max_depth"]
    u[0, 1, 0, 0] = expected_obs[0]["U"]["surface"]
    u[1, 0, 1, 1] = expected_obs[1]["U"]["max_depth"]
    u[1, 1, 1, 1] = expected_obs[1]["U"]["surface"]

    # make ds
    times = np.array([expected_obs[0]["time"], expected_obs[1]["time"]])
    lats = np.array([expected_obs[0]["lat"], expected_obs[1]["lat"]])
    lons = np.array([expected_obs[0]["lon"], expected_obs[1]["lon"]])

    ds_fields = xr.Dataset(
        data_vars={
            "U": (["time", "depth", "lat", "lon"], u, {"units": "m s-1"}),
            "V": (["time", "depth", "lat", "lon"], v, {"units": "m s-1"}),
        },
        coords={
            "time": ("time", times, {"axis": "T"}),
            "depth": ("depth", [MAX_DEPTH, MIN_DEPTH], {"units": "m", "axis": "Z"}),
            "lat": ("lat", lats, {"units": "degrees_north"}),
            "lon": ("lon", lons, {"units": "degrees_east"}),
        },
    )

    # to fieldset
    fields = {"U": ds_fields["U"], "V": ds_fields["V"]}
    ds_fset = parcels.convert.copernicusmarine_to_sgrid(fields=fields)
    fieldset = parcels.FieldSet.from_sgrid_conventions(ds_fset)

    adcp_instrument = ADCPInstrument(adcp_expedition, from_data=None)
    out_path = tmpdir.join("out.parquet")

    adcp_instrument.load_input_data = lambda: fieldset
    adcp_instrument.simulate(sample_points, out_path)

    results = parcels.read_particlefile(out_path)

    assert np.unique(results["z"].to_numpy()).size == NUM_BINS

    # for every obs, check if the variables match the expected observations
    # we only verify at the surface and max depth of the adcp, because in between is tricky
    for df_depth, vert_loc in [
        (results.filter(pl.col("z") == MAX_DEPTH), "max_depth"),
        (results.filter(pl.col("z") == MIN_DEPTH), "surface"),
    ]:
        assert len(df_depth) == len(sample_points)

        for i, (obs_i, exp) in enumerate(
            zip(df_depth.iter_rows(named=True), expected_obs, strict=True)
        ):
            for var in [("y", "lat"), ("x", "lon")]:
                obs_value = obs_i[var[0]]
                exp_value = exp[var[1]]
                assert np.isclose(obs_value, exp_value), (
                    f"Observation incorrect {vert_loc=} {obs_i=} {var=} {obs_value=} {exp_value=}."
                )
            for var in ["V", "U"]:
                obs_value = obs_i[var]
                exp_value = exp[var][vert_loc]
                assert np.isclose(obs_value, exp_value), (
                    f"Observation incorrect {vert_loc=} {i=} {var=} {obs_value=} {exp_value=}."
                )


def test_adcp_sensor_config_active_variables() -> None:
    """active_variables() returns both U and V when VELOCITY is enabled."""
    config_with = ADCPConfig(
        max_depth_meter=-1000.0,
        num_bins=40,
        period_minutes=5.0,
        sensors=[SensorConfig(sensor_type=SensorType.VELOCITY)],
    )
    assert config_with.active_variables() == {"U": "uo", "V": "vo"}


def test_adcp_sensor_config_yaml() -> None:
    """ADCPConfig sensors survive YAML serialisation."""
    config = ADCPConfig(
        max_depth_meter=-1000.0,
        num_bins=40,
        period_minutes=5.0,
        sensors=[SensorConfig(sensor_type=SensorType.VELOCITY)],
    )
    dumped = config.model_dump(by_alias=True)
    loaded = ADCPConfig.model_validate(dumped)
    assert len(loaded.sensors) == 1
    assert loaded.sensors[0].sensor_type == SensorType.VELOCITY
    assert loaded.sensors[0].enabled is True


def test_adcp_config_default_sensors():
    """ADCPConfig defaults to VELOCITY."""
    config = ADCPConfig(
        max_depth_meter=-500.0,
        num_bins=30,
        period_minutes=30.0,
    )
    assert config.sensors[0].sensor_type is SensorType.VELOCITY


def test_adcp_config_unsupported_sensor_rejected():
    """Unsupported sensor on ADCP is rejected."""
    with pytest.raises(pydantic.ValidationError, match="does not support"):
        ADCPConfig(
            max_depth_meter=-500.0,
            num_bins=30,
            period_minutes=30.0,
            sensors=[SensorConfig(sensor_type=SensorType.TEMPERATURE)],
        )


def test_adcp_instrument_type(adcp_expedition):
    """ADCPInstrument returns the correct InstrumentType and if is underway instrument."""
    adcp_instrument = ADCPInstrument(adcp_expedition, from_data=None)
    assert adcp_instrument.instrument_type == InstrumentType.ADCP
    assert adcp_instrument.instrument_type.is_underway
