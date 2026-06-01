"""Test the simulation of Argo floats."""

from datetime import datetime, timedelta

import numpy as np
import pydantic
import pytest
import xarray as xr
from parcels import FieldSet

from virtualship.instruments.argo_float import ArgoFloat, ArgoFloatInstrument
from virtualship.instruments.sensors import SensorType
from virtualship.models import Location, Spacetime
from virtualship.models.expedition import (
    ArgoFloatConfig,
    InstrumentsConfig,
    SensorConfig,
    Waypoint,
)


def test_simulate_argo_floats(tmpdir) -> None:
    # arbitrary time offset for the dummy fieldset
    base_time = datetime.strptime("1950-01-01", "%Y-%m-%d")

    DRIFT_DEPTH = -1000
    MAX_DEPTH = -2000
    VERTICAL_SPEED = -0.10
    CYCLE_DAYS = 10
    DRIFT_DAYS = 9
    LIFETIME = timedelta(days=1)

    CONST_TEMPERATURE = 1.0  # constant temperature in fieldset
    CONST_SALINITY = 1.0  # constant salinity in fieldset

    v = np.full((2, 2, 2), 1.0)
    u = np.full((2, 2, 2), 1.0)
    t = np.full((2, 2, 2), CONST_TEMPERATURE)
    s = np.full((2, 2, 2), CONST_SALINITY)
    bathy = np.full((2, 2), -5000.0)

    fieldset = FieldSet.from_data(
        {"V": v, "U": u, "T": t, "S": s},
        {
            "lon": np.array([0.0, 10.0]),
            "lat": np.array([0.0, 10.0]),
            "time": [
                np.datetime64(base_time + timedelta(seconds=0)),
                np.datetime64(base_time + timedelta(hours=4)),
            ],
        },
    )
    fieldset.add_field(
        FieldSet.from_data(
            {"bathymetry": bathy},
            {
                "lon": np.array([0.0, 10.0]),
                "lat": np.array([0.0, 10.0]),
            },
        ).bathymetry
    )

    # argo floats to deploy
    argo_floats = [
        ArgoFloat(
            spacetime=Spacetime(location=Location(latitude=0, longitude=0), time=0),
            min_depth=0.0,
            max_depth=MAX_DEPTH,
            drift_depth=DRIFT_DEPTH,
            vertical_speed=VERTICAL_SPEED,
            cycle_days=CYCLE_DAYS,
            drift_days=DRIFT_DAYS,
        )
    ]

    # dummy expedition for ArgoFloatInstrument
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
            argo_float_config=ArgoFloatConfig(
                min_depth_meter=0.0,
                max_depth_meter=MAX_DEPTH,
                drift_depth_meter=DRIFT_DEPTH,
                vertical_speed_meter_per_second=VERTICAL_SPEED,
                cycle_days=CYCLE_DAYS,
                drift_days=DRIFT_DAYS,
                lifetime=LIFETIME,
                stationkeeping_time_minutes=10,
                sensors=[
                    SensorConfig(sensor_type=SensorType.TEMPERATURE),
                    SensorConfig(sensor_type=SensorType.SALINITY),
                ],
            )
        )

    expedition = DummyExpedition()
    from_data = None

    argo_instrument = ArgoFloatInstrument(expedition, from_data)
    out_path = tmpdir.join("out.zarr")

    argo_instrument.load_input_data = lambda: fieldset
    argo_instrument.simulate(argo_floats, out_path)

    # test if output is as expected
    results = xr.open_zarr(out_path)

    # check the following variables are in the dataset
    assert len(results.trajectory) == len(argo_floats)
    for var in ["lon", "lat", "z", "temperature", "salinity"]:
        assert var in results, f"Results don't contain {var}"


def test_argo_float_disabled_sensor(tmpdir) -> None:
    """Variables for disabled sensors must not appear in the zarr output."""
    base_time = datetime.strptime("1950-01-01", "%Y-%m-%d")

    DRIFT_DEPTH = -1000
    MAX_DEPTH = -2000
    VERTICAL_SPEED = -0.10
    CYCLE_DAYS = 10
    DRIFT_DAYS = 9
    LIFETIME = timedelta(days=1)

    v = np.full((2, 2, 2), 1.0)
    u = np.full((2, 2, 2), 1.0)
    t = np.full((2, 2, 2), 1.0)
    bathy = np.full((2, 2), -5000.0)

    # only temperature fieldset, no salinity
    fieldset = FieldSet.from_data(
        {"V": v, "U": u, "T": t},
        {
            "lon": np.array([0.0, 10.0]),
            "lat": np.array([0.0, 10.0]),
            "time": [
                np.datetime64(base_time + timedelta(seconds=0)),
                np.datetime64(base_time + timedelta(hours=4)),
            ],
        },
    )
    fieldset.add_field(
        FieldSet.from_data(
            {"bathymetry": bathy},
            {"lon": np.array([0.0, 10.0]), "lat": np.array([0.0, 10.0])},
        ).bathymetry
    )

    argo_floats = [
        ArgoFloat(
            spacetime=Spacetime(location=Location(latitude=0, longitude=0), time=0),
            min_depth=0.0,
            max_depth=MAX_DEPTH,
            drift_depth=DRIFT_DEPTH,
            vertical_speed=VERTICAL_SPEED,
            cycle_days=CYCLE_DAYS,
            drift_days=DRIFT_DAYS,
        )
    ]

    class DummyExpedition:
        class schedule:
            waypoints = [Waypoint(location=Location(1, 2), time=base_time)]

        instruments_config = InstrumentsConfig(
            argo_float_config=ArgoFloatConfig(
                min_depth_meter=0.0,
                max_depth_meter=MAX_DEPTH,
                drift_depth_meter=DRIFT_DEPTH,
                vertical_speed_meter_per_second=VERTICAL_SPEED,
                cycle_days=CYCLE_DAYS,
                drift_days=DRIFT_DAYS,
                lifetime=LIFETIME,
                stationkeeping_time_minutes=10,
                sensors=[
                    SensorConfig(sensor_type=SensorType.TEMPERATURE)
                ],  # SALINITY omitted = disabled
            )
        )

    expedition = DummyExpedition()
    argo_instrument = ArgoFloatInstrument(expedition, None)
    out_path = tmpdir.join("out_disabled.zarr")
    argo_instrument.load_input_data = lambda: fieldset
    argo_instrument.simulate(argo_floats, out_path)

    results = xr.open_zarr(out_path)
    assert "temperature" in results, "Enabled sensor variable must be present"
    assert "salinity" not in results, (
        "Disabled sensor variable must be absent from output"
    )


def test_argo_config_default_sensors():
    """ArgoFloatConfig defaults to TEMPERATURE + SALINITY."""
    config = ArgoFloatConfig(
        min_depth_meter=0.0,
        max_depth_meter=-2000,
        drift_depth_meter=-1000,
        vertical_speed_meter_per_second=-0.10,
        cycle_days=10,
        drift_days=9,
        lifetime=timedelta(days=30),
        stationkeeping_time_minutes=10,
    )
    types = {sc.sensor_type for sc in config.sensors}
    assert types == {SensorType.TEMPERATURE, SensorType.SALINITY}


def test_argo_config_unsupported_sensor_rejected():
    """Unsupported sensor on ArgoFloat is rejected."""
    with pytest.raises(pydantic.ValidationError, match="does not support"):
        ArgoFloatConfig(
            min_depth_meter=0.0,
            max_depth_meter=-2000,
            drift_depth_meter=-1000,
            vertical_speed_meter_per_second=-0.10,
            cycle_days=10,
            drift_days=9,
            lifetime=timedelta(days=30),
            stationkeeping_time_minutes=10,
            sensors=[SensorConfig(sensor_type=SensorType.OXYGEN)],
        )


def test_argo_config_drift_days_exceeds_cycle_days():
    """ArgoFloatConfig should reject drift_days >= cycle_days."""
    base_kwargs = {
        "min_depth_meter": 0.0,
        "max_depth_meter": -2000,
        "drift_depth_meter": -1000,
        "vertical_speed_meter_per_second": -0.10,
        "lifetime": timedelta(days=30),
        "stationkeeping_time_minutes": 10,
    }

    # drift_days > cycle_days should raise validation error
    with pytest.raises(
        pydantic.ValidationError, match="drift_days .* must be less than cycle_days"
    ):
        ArgoFloatConfig(**base_kwargs, cycle_days=10, drift_days=15)

    # drift_days == cycle_days should also raise validation error
    with pytest.raises(
        pydantic.ValidationError, match="drift_days .* must be less than cycle_days"
    ):
        ArgoFloatConfig(**base_kwargs, cycle_days=10, drift_days=10)

    # check a valid configuration: drift_days < cycle_days
    config = ArgoFloatConfig(**base_kwargs, cycle_days=10, drift_days=9)
    assert config.drift_days == 9
    assert config.cycle_days == 10


def test_argo_fieldoutofbounds_error(tmpdir, capsys) -> None:
    """
    Test Argo Float handles Parcels FieldOutOfBoundsError when it drifts outside the fieldset, but does not exit the simulation.

    The check is housed in the Instrument base class, but we test it here in the context of ArgoFloat since it is the only instrument (at time of writing) that can drift out of bounds (Drifters have unbounded fieldsets).
    """
    # arbitrary time offset for the dummy fieldset
    base_time = datetime.strptime("1950-01-01", "%Y-%m-%d")

    DRIFT_DEPTH = -1000
    MAX_DEPTH = -2000
    VERTICAL_SPEED = -0.10
    CYCLE_DAYS = 10
    DRIFT_DAYS = 9
    LIFETIME = timedelta(days=3)  # give time to drift out of bounds

    CONST_TEMPERATURE = 1.0  # constant temperature in fieldset
    CONST_SALINITY = 1.0  # constant salinity in fieldset

    v = np.full((2, 2, 2), 1.0)
    u = np.full((2, 2, 2), 1.0)
    t = np.full((2, 2, 2), CONST_TEMPERATURE)
    s = np.full((2, 2, 2), CONST_SALINITY)
    bathy = np.full((2, 2), -5000.0)

    # small fieldset
    LON_MIN, LON_MAX = 0.0, 0.1
    LAT_MIN, LAT_MAX = 0.0, 0.1
    fieldset = FieldSet.from_data(
        {"V": v, "U": u, "T": t, "S": s},
        {
            "lon": np.array([LON_MIN, LON_MAX]),
            "lat": np.array([LAT_MIN, LAT_MAX]),
            "time": [
                np.datetime64(base_time + timedelta(seconds=0)),
                np.datetime64(
                    base_time + timedelta(days=LIFETIME.days + 1)
                ),  # ensure fieldset covers entire simulation period
            ],
        },
    )
    fieldset.add_field(
        FieldSet.from_data(
            {"bathymetry": bathy},
            {
                "lon": np.array([LON_MIN, LON_MAX]),
                "lat": np.array([LAT_MIN, LAT_MAX]),
            },
        ).bathymetry
    )

    # argo floats to deploy
    argo_floats = [
        ArgoFloat(
            spacetime=Spacetime(location=Location(latitude=0, longitude=0), time=0),
            min_depth=0.0,
            max_depth=MAX_DEPTH,
            drift_depth=DRIFT_DEPTH,
            vertical_speed=VERTICAL_SPEED,
            cycle_days=CYCLE_DAYS,
            drift_days=DRIFT_DAYS,
        )
    ]

    # dummy expedition for ArgoFloatInstrument
    class DummyExpedition:
        class schedule:
            # ruff: noqa
            waypoints = [
                Waypoint(
                    location=Location(0.0, 0.0),
                    time=base_time,
                ),
            ]

        instruments_config = InstrumentsConfig(
            argo_float_config=ArgoFloatConfig(
                min_depth_meter=0.0,
                max_depth_meter=MAX_DEPTH,
                drift_depth_meter=DRIFT_DEPTH,
                vertical_speed_meter_per_second=VERTICAL_SPEED,
                cycle_days=CYCLE_DAYS,
                drift_days=DRIFT_DAYS,
                lifetime=LIFETIME,
                stationkeeping_time_minutes=10,
                sensors=[
                    SensorConfig(sensor_type=SensorType.TEMPERATURE),
                    SensorConfig(sensor_type=SensorType.SALINITY),
                ],
            )
        )

    expedition = DummyExpedition()
    from_data = None

    argo_instrument = ArgoFloatInstrument(expedition, from_data)
    out_path = tmpdir.join("out.zarr")

    argo_instrument.load_input_data = lambda: fieldset
    argo_instrument.simulate(argo_floats, out_path)

    # test if output is as expected; results file should exist even if data is incomplete due to out-of-bounds error, and simulation should not crash
    results = xr.open_zarr(out_path)

    # not reaching expected final time indicates simulation was stopped due to FieldOutOfBounds error
    expected_final_time = np.datetime64(base_time + LIFETIME)
    actual_final_time = results.time.values[np.isfinite(results.time.values)].max()
    assert actual_final_time < expected_final_time, (
        "Actual final time should be less than expected final time due to out-of-bounds error/warning"
    )

    # TODO: capturing the warnings in the tests is complicated by the Parcels C-level print statements; but the logic of not crashing on out-of-bounds is tested if the test simulation runs
    # TODO: when using Parcels v4, this test can become much more robust by capturing the specific warning as well
