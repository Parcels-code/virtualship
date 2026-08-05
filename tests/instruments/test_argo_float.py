"""Test the simulation of Argo floats."""

import contextlib
import io
from datetime import datetime, timedelta

import numpy as np
import parcels
import pydantic
import pytest
import xarray as xr

from virtualship.instruments.argo_float import ArgoFloat, ArgoFloatInstrument
from virtualship.instruments.sensors import SensorType
from virtualship.instruments.types import InstrumentType
from virtualship.models import Location, Spacetime
from virtualship.models.expedition import (
    ArgoFloatConfig,
    InstrumentsConfig,
    SensorConfig,
    Waypoint,
)

# Constants
BASE_TIME = datetime.strptime("1950-01-01", "%Y-%m-%d")
DRIFT_DEPTH = -1000
MAX_DEPTH = -2000
VERTICAL_SPEED = -0.10
CYCLE_DAYS = 10
DRIFT_DAYS = 9
STATIONKEEPING_TIME = 10


@pytest.fixture
def argo_config_kwargs():
    """Common ArgoFloatConfig parameters."""
    return {
        "min_depth_meter": 0.0,
        "max_depth_meter": MAX_DEPTH,
        "drift_depth_meter": DRIFT_DEPTH,
        "vertical_speed_meter_per_second": VERTICAL_SPEED,
        "cycle_days": CYCLE_DAYS,
        "drift_days": DRIFT_DAYS,
        "stationkeeping_time_minutes": STATIONKEEPING_TIME,
    }


def create_fieldset(
    lon_range=(0.0, 10.0),
    lat_range=(0.0, 10.0),
    include_salinity=True,
    lifetime_days=0.1,
):
    """Create a test fieldset with optional salinity."""
    v = np.full((2, 2, 2), 1.0)
    u = np.full((2, 2, 2), 1.0)
    t = np.full((2, 2, 2), 1.0)
    bathy = np.full((2, 2), -5000.0)

    data_vars = {
        "V": (("time", "lat", "lon"), v),
        "U": (("time", "lat", "lon"), u),
        "T": (("time", "lat", "lon"), t),
    }

    if include_salinity:
        data_vars["S"] = (("time", "lat", "lon"), np.full((2, 2, 2), 1.0))

    ds_fields = xr.Dataset(
        data_vars=data_vars,
        coords={
            "lon": (("lon"), np.array(lon_range), {"units": "degrees_east"}),
            "lat": (("lat"), np.array(lat_range), {"units": "degrees_north"}),
            "time": (
                ("time"),
                [
                    np.datetime64(BASE_TIME),
                    np.datetime64(BASE_TIME + timedelta(days=lifetime_days)),
                ],
                {"axis": "T"},
            ),
        },
    )

    fields = {var: ds_fields[var] for var in data_vars.keys()}
    ds_fset = parcels.convert.copernicusmarine_to_sgrid(fields=fields)
    fieldset = parcels.FieldSet.from_sgrid_conventions(ds_fset)

    ds_bathymetry = xr.Dataset(
        data_vars={"bathymetry": (("lat", "lon"), bathy)},
        coords={
            "lon": (("lon"), np.array(lon_range), {"units": "degrees_east"}),
            "lat": (("lat"), np.array(lat_range), {"units": "degrees_north"}),
        },
    )
    ds_bathymetry_fset = parcels.convert.copernicusmarine_to_sgrid(
        fields={"bathymetry": ds_bathymetry["bathymetry"]}
    )
    bathymetry_fset = parcels.FieldSet.from_sgrid_conventions(ds_bathymetry_fset)

    fieldset.add_field(bathymetry_fset.bathymetry)

    return fieldset


def create_argo_float(waypoint):
    """Create a single ArgoFloat instance."""
    return ArgoFloat(
        spacetime=Spacetime(
            location=Location(
                latitude=waypoint.location.latitude,
                longitude=waypoint.location.longitude,
            ),
            time=waypoint.time,
        ),
        min_depth=0.0,
        max_depth=MAX_DEPTH,
        drift_depth=DRIFT_DEPTH,
        vertical_speed=VERTICAL_SPEED,
        cycle_days=CYCLE_DAYS,
        drift_days=DRIFT_DAYS,
    )


def create_dummy_expedition(sensors, lifetime=timedelta(days=1), location=(1, 2)):
    """Create a DummyExpedition class with specified sensors and parameters."""

    class DummyExpedition:
        class schedule:
            waypoints: list[Waypoint] = [  # noqa: RUF012
                Waypoint(location=Location(*location), time=BASE_TIME)
            ]

        instruments_config = InstrumentsConfig(
            argo_float_config=ArgoFloatConfig(
                min_depth_meter=0.0,
                max_depth_meter=MAX_DEPTH,
                drift_depth_meter=DRIFT_DEPTH,
                vertical_speed_meter_per_second=VERTICAL_SPEED,
                cycle_days=CYCLE_DAYS,
                drift_days=DRIFT_DAYS,
                lifetime=lifetime,
                stationkeeping_time_minutes=STATIONKEEPING_TIME,
                sensors=sensors,
            )
        )

    return DummyExpedition()


def test_simulate_argo_floats(tmpdir) -> None:
    """Test basic Argo float simulation with temperature and salinity sensors."""
    fieldset = create_fieldset()

    sensors = [
        SensorConfig(sensor_type=SensorType.TEMPERATURE),
        SensorConfig(sensor_type=SensorType.SALINITY),
    ]
    expedition = create_dummy_expedition(sensors)

    argo_instrument = ArgoFloatInstrument(expedition, None)
    argo_floats = [create_argo_float(wp) for wp in expedition.schedule.waypoints]
    out_path = tmpdir.join("out.parquet")
    argo_instrument.load_input_data = lambda: fieldset
    argo_instrument.simulate(argo_floats, out_path)

    results = parcels.read_particlefile(out_path)
    assert np.unique(results["particle_id"].to_numpy()).size == len(argo_floats)
    for var in ["x", "y", "z", "temperature", "salinity"]:
        assert var in results, f"Results don't contain {var}"


def test_argo_float_disabled_sensor(tmpdir) -> None:
    """Variables for disabled sensors must not appear in the zarr output."""
    fieldset = create_fieldset(include_salinity=False)

    # only temperature sensor enabled
    sensors = [SensorConfig(sensor_type=SensorType.TEMPERATURE)]
    expedition = create_dummy_expedition(sensors)

    argo_instrument = ArgoFloatInstrument(expedition, None)
    argo_floats = [create_argo_float(wp) for wp in expedition.schedule.waypoints]
    out_path = tmpdir.join("out_disabled.parquet")
    argo_instrument.load_input_data = lambda: fieldset
    argo_instrument.simulate(argo_floats, out_path)

    results = parcels.read_particlefile(out_path)
    assert "temperature" in results, "Enabled sensor variable must be present"
    assert "salinity" not in results, (
        "Disabled sensor variable must be absent from output"
    )


def test_argo_config_default_sensors(argo_config_kwargs):
    """ArgoFloatConfig defaults to TEMPERATURE + SALINITY."""
    config = ArgoFloatConfig(**argo_config_kwargs, lifetime=timedelta(days=30))
    types = {sc.sensor_type for sc in config.sensors}
    assert types == {SensorType.TEMPERATURE, SensorType.SALINITY}


def test_argo_config_unsupported_sensor_rejected(argo_config_kwargs):
    """Unsupported sensor on ArgoFloat is rejected."""
    with pytest.raises(pydantic.ValidationError, match="does not support"):
        ArgoFloatConfig(
            **argo_config_kwargs,
            lifetime=timedelta(days=30),
            sensors=[SensorConfig(sensor_type=SensorType.OXYGEN)],
        )


def test_argo_config_drift_days_exceeds_cycle_days(argo_config_kwargs):
    """ArgoFloatConfig should reject drift_days >= cycle_days."""
    base_kwargs = {**argo_config_kwargs, "lifetime": timedelta(days=30)}

    # remove cycle_days and drift_days from base_kwargs since override here
    base_kwargs.pop("cycle_days", None)
    base_kwargs.pop("drift_days", None)

    # drift_days > cycle_days should raise validation error
    with pytest.raises(
        pydantic.ValidationError, match=r"drift_days .* must be less than cycle_days"
    ):
        ArgoFloatConfig(**base_kwargs, cycle_days=10, drift_days=15)

    # drift_days == cycle_days should also raise validation error
    with pytest.raises(
        pydantic.ValidationError, match=r"drift_days .* must be less than cycle_days"
    ):
        ArgoFloatConfig(**base_kwargs, cycle_days=10, drift_days=10)

    # check a valid configuration: drift_days < cycle_days
    config = ArgoFloatConfig(**base_kwargs, cycle_days=10, drift_days=9)
    assert config.drift_days == 9
    assert config.cycle_days == 10


def test_argo_fieldoutofbounds_error(tmpdir) -> None:
    """
    Test Argo Float handles Parcels FieldOutOfBoundsError.

    When it drifts outside the fieldset, it should not exit the simulation.
    """
    lifetime = timedelta(days=3)  # give time to drift out of bounds

    # small fieldset to ensure float drifts out of bounds
    fieldset = create_fieldset(
        lon_range=(0.0, 0.1), lat_range=(0.0, 0.1), lifetime_days=lifetime.days
    )

    sensors = [
        SensorConfig(sensor_type=SensorType.TEMPERATURE),
        SensorConfig(sensor_type=SensorType.SALINITY),
    ]
    expedition = create_dummy_expedition(
        sensors, lifetime=lifetime, location=(0.0, 0.0)
    )

    argo_instrument = ArgoFloatInstrument(expedition, None)
    argo_floats = [create_argo_float(wp) for wp in expedition.schedule.waypoints]

    out_path = tmpdir.join("out.parquet")
    argo_instrument.load_input_data = lambda: fieldset

    # capture stdout/stderr safely without breaking (i.e. using capsys interferes with print out stream...)
    f = io.StringIO()
    with contextlib.redirect_stdout(f), contextlib.redirect_stderr(f):
        argo_instrument.simulate(argo_floats, out_path)

    output_log = f.getvalue()

    # results file should exist even if data is incomplete due to out-of-bounds error
    results = parcels.read_particlefile(out_path)

    # not reaching expected final time indicates simulation was stopped due to FieldOutOfBounds
    expected_final_time = np.datetime64(BASE_TIME + lifetime)
    actual_final_time = (
        results["t"].to_numpy()[np.isfinite(results["t"].to_numpy())].max()
    )
    assert actual_final_time < expected_final_time, (
        "Actual final time should be less than expected final time due to out-of-bounds error/warning"
    )

    assert "ErrorOutOfBounds" in output_log, (
        "Expected 'ErrorOutOfBounds' message to be printed during simulation."
    )


def test_argo_float_instrument_type():
    """ArgoFloatInstrument returns the correct InstrumentType and if is underway instrument."""
    sensors = [
        SensorConfig(sensor_type=SensorType.TEMPERATURE),
        SensorConfig(sensor_type=SensorType.SALINITY),
    ]
    expedition = create_dummy_expedition(sensors)

    argo_instrument = ArgoFloatInstrument(expedition, from_data=None)
    assert argo_instrument.instrument_type == InstrumentType.ARGO_FLOAT
    assert not argo_instrument.instrument_type.is_underway
