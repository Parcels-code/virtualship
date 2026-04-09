"""
Test the simulation of CTD instruments.

Fields are kept static over time and time component of CTD measurements is not tested tested because it's tricky to provide expected measurements.
"""

import datetime

import numpy as np
import pydantic
import pytest
import xarray as xr

from parcels import Field, FieldSet
from virtualship.instruments.ctd import CTD, CTDInstrument
from virtualship.instruments.sensors import CTD_SUPPORTED_SENSORS, SensorType
from virtualship.models import Location, Spacetime
from virtualship.models.expedition import (
    CTDConfig,
    InstrumentsConfig,
    SensorConfig,
    Waypoint,
)


def test_simulate_ctds(tmpdir) -> None:
    # arbitrary time offset for the dummy fieldset
    base_time = datetime.datetime.strptime("1950-01-01", "%Y-%m-%d")

    # where to cast CTDs
    ctds = [
        CTD(
            spacetime=Spacetime(
                location=Location(latitude=0, longitude=1),
                time=base_time + datetime.timedelta(hours=0),
            ),
            min_depth=0,
            max_depth=float("-inf"),
        ),
        CTD(
            spacetime=Spacetime(
                location=Location(latitude=1, longitude=0),
                time=base_time,
            ),
            min_depth=0,
            max_depth=float("-inf"),
        ),
    ]

    # expected observations for ctds at surface and at maximum depth
    ctd_exp = [
        {
            "surface": {
                "salinity": 5,
                "temperature": 6,
                "lat": ctds[0].spacetime.location.lat,
                "lon": ctds[0].spacetime.location.lon,
            },
            "maxdepth": {
                "salinity": 7,
                "temperature": 8,
                "lat": ctds[0].spacetime.location.lat,
                "lon": ctds[0].spacetime.location.lon,
            },
        },
        {
            "surface": {
                "salinity": 5,
                "temperature": 6,
                "lat": ctds[1].spacetime.location.lat,
                "lon": ctds[1].spacetime.location.lon,
            },
            "maxdepth": {
                "salinity": 7,
                "temperature": 8,
                "lat": ctds[1].spacetime.location.lat,
                "lon": ctds[1].spacetime.location.lon,
            },
        },
    ]

    # create fieldset based on the expected observations
    # indices are time, depth, latitude, longitude
    u = np.zeros((2, 2, 2, 2))
    v = np.zeros((2, 2, 2, 2))
    t = np.zeros((2, 2, 2, 2))
    s = np.zeros((2, 2, 2, 2))

    t[:, 1, 0, 1] = ctd_exp[0]["surface"]["temperature"]
    t[:, 0, 0, 1] = ctd_exp[0]["maxdepth"]["temperature"]
    t[:, 1, 1, 0] = ctd_exp[1]["surface"]["temperature"]
    t[:, 0, 1, 0] = ctd_exp[1]["maxdepth"]["temperature"]

    s[:, 1, 0, 1] = ctd_exp[0]["surface"]["salinity"]
    s[:, 0, 0, 1] = ctd_exp[0]["maxdepth"]["salinity"]
    s[:, 1, 1, 0] = ctd_exp[1]["surface"]["salinity"]
    s[:, 0, 1, 0] = ctd_exp[1]["maxdepth"]["salinity"]

    fieldset = FieldSet.from_data(
        {"V": v, "U": u, "T": t, "S": s},
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

    # dummy expedition for CTDInstrument
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
            ctd_config=CTDConfig(
                stationkeeping_time_minutes=50,
                min_depth_meter=-11.0,
                max_depth_meter=-2000.0,
                sensors=[
                    SensorConfig(sensor_type=SensorType.TEMPERATURE),
                    SensorConfig(sensor_type=SensorType.SALINITY),
                ],
            )
        )

    expedition = DummyExpedition()
    from_data = None

    ctd_instrument = CTDInstrument(expedition, from_data)
    out_path = tmpdir.join("out.zarr")

    ctd_instrument.load_input_data = lambda: fieldset
    ctd_instrument.simulate(ctds, out_path)

    # test if output is as expected
    results = xr.open_zarr(out_path)

    assert len(results.trajectory) == len(ctds)

    for ctd_i, (traj, exp_bothloc) in enumerate(
        zip(results.trajectory, ctd_exp, strict=True)
    ):
        obs_surface = results.sel(trajectory=traj, obs=0)
        min_index = np.argmin(results.sel(trajectory=traj)["z"].data)
        obs_maxdepth = results.sel(trajectory=traj, obs=min_index)

        for obs, loc in [
            (obs_surface, "surface"),
            (obs_maxdepth, "maxdepth"),
        ]:
            exp = exp_bothloc[loc]
            for var in ["salinity", "temperature", "lat", "lon"]:
                obs_value = obs[var].values.item()
                exp_value = exp[var]

                assert np.isclose(obs_value, exp_value), (
                    f"Observation incorrect {ctd_i=} {loc=} {var=} {obs_value=} {exp_value=}."
                )


def test_ctd_sensor_config_active_variables() -> None:
    """active_variables() only returns variables for enabled sensors."""
    config_both = CTDConfig(
        stationkeeping_time_minutes=50,
        min_depth_meter=-11.0,
        max_depth_meter=-2000.0,
        sensors=[
            SensorConfig(sensor_type=SensorType.TEMPERATURE),
            SensorConfig(sensor_type=SensorType.SALINITY),
        ],
    )
    assert config_both.active_variables() == {"T": "thetao", "S": "so"}

    config_temp_only = CTDConfig(
        stationkeeping_time_minutes=50,
        min_depth_meter=-11.0,
        max_depth_meter=-2000.0,
        sensors=[
            SensorConfig(sensor_type=SensorType.TEMPERATURE)
        ],  # SALINITY absent = disabled
    )
    assert config_temp_only.active_variables() == {"T": "thetao"}

    with pytest.raises(pydantic.ValidationError, match="no enabled sensors"):
        CTDConfig(
            stationkeeping_time_minutes=50,
            min_depth_meter=-11.0,
            max_depth_meter=-2000.0,
            sensors=[],  # all absent = all disabled → invalid
        )


def test_ctd_sensor_config_yaml() -> None:
    """CTDConfig sensors survive YAML serialisation."""
    config = CTDConfig(
        stationkeeping_time_minutes=50,
        min_depth_meter=-11.0,
        max_depth_meter=-2000.0,
        sensors=[
            SensorConfig(sensor_type=SensorType.TEMPERATURE)
        ],  # SALINITY omitted = disabled
    )
    dumped = config.model_dump(by_alias=True)
    loaded = CTDConfig.model_validate(dumped)

    assert len(loaded.sensors) == 1
    assert loaded.sensors[0].sensor_type == SensorType.TEMPERATURE
    assert loaded.sensors[0].enabled is True


def test_ctd_disabled_sensor_absent(tmpdir) -> None:
    """Variables for disabled sensors must not appear in the zarr output."""
    base_time = datetime.datetime.strptime("1950-01-01", "%Y-%m-%d")

    ctds = [
        CTD(
            spacetime=Spacetime(
                location=Location(latitude=0, longitude=0),
                time=base_time,
            ),
            min_depth=0,
            max_depth=-20,
        ),
    ]

    # Only temperature field, no salinty
    t = np.full((2, 2, 2), 5.0)
    fieldset = FieldSet.from_data(
        {"T": t},
        {
            "lon": np.array([0.0, 1.0]),
            "lat": np.array([0.0, 1.0]),
            "time": [
                np.datetime64(base_time + datetime.timedelta(seconds=0)),
                np.datetime64(base_time + datetime.timedelta(hours=4)),
            ],
        },
    )
    fieldset.add_field(Field("bathymetry", [-1000], lon=0, lat=0))

    class DummyExpedition:
        class schedule:
            waypoints = [Waypoint(location=Location(1, 2), time=base_time)]

        instruments_config = InstrumentsConfig(
            ctd_config=CTDConfig(
                stationkeeping_time_minutes=50,
                min_depth_meter=-11.0,
                max_depth_meter=-2000.0,
                sensors=[
                    SensorConfig(sensor_type=SensorType.TEMPERATURE)
                ],  # SALINITY omitted = disabled
            )
        )

    expedition = DummyExpedition()
    ctd_instrument = CTDInstrument(expedition, None)
    out_path = tmpdir.join("out_disabled.zarr")
    ctd_instrument.load_input_data = lambda: fieldset
    ctd_instrument.simulate(ctds, out_path)

    results = xr.open_zarr(out_path)
    assert "temperature" in results, "Enabled sensor variable must be present"
    assert "salinity" not in results, (
        "Disabled sensor variable must be absent from output"
    )


def test_ctd_supported_sensors():
    """CTD supports TEMPERATURE and SALINITY."""
    assert CTD_SUPPORTED_SENSORS == frozenset(
        {SensorType.TEMPERATURE, SensorType.SALINITY}
    )


def test_ctd_config_default_sensors():
    """CTDConfig defaults to TEMPERATURE + SALINITY."""
    config = CTDConfig(
        stationkeeping_time_minutes=50,
        min_depth_meter=-11.0,
        max_depth_meter=-2000.0,
    )
    types = {sc.sensor_type for sc in config.sensors}
    assert types == {SensorType.TEMPERATURE, SensorType.SALINITY}


# TODO: may need to be removed if add ADCP to CTDs in future PR...
def test_ctd_config_unsupported_sensor_rejected():
    """Unsupported sensor on CTD is rejected."""
    with pytest.raises(pydantic.ValidationError, match="does not support"):
        CTDConfig(
            stationkeeping_time_minutes=50,
            min_depth_meter=-11.0,
            max_depth_meter=-2000.0,
            sensors=[SensorConfig(sensor_type=SensorType.VELOCITY)],
        )
