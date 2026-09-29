"""Test the simulation of Argo floats."""

import contextlib
import io
from datetime import datetime, timedelta
from typing import ClassVar

import numpy as np
import parcels
import polars as pl
import pydantic
import pytest
import xarray as xr

from virtualship.instruments.argo_float import (
    ArgoFloat,
    ArgoFloatInstrument,
    _handle_grounding,
    _keep_at_surface,
)
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
    depths=None,
):
    """Create a test fieldset with optional salinity and optional depth levels."""
    dims = ("time", "lat", "lon") if depths is None else ("time", "depth", "lat", "lon")
    shape = (2, 2, 2) if depths is None else (2, len(depths), 2, 2)
    bathy = np.full((2, 2), -5000.0)

    data_vars = {
        "V": (dims, np.full(shape, 1.0)),
        "U": (dims, np.full(shape, 1.0)),
        "T": (dims, np.full(shape, 1.0)),
    }

    if include_salinity:
        data_vars["S"] = (dims, np.full(shape, 1.0))

    depth_coord = (
        {}
        if depths is None
        else {"depth": (("depth"), np.array(depths), {"positive": "up"})}
    )

    ds_fields = xr.Dataset(
        data_vars=data_vars,
        coords={
            **depth_coord,
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

    return fieldset + bathymetry_fset


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

    class DummySchedule:
        waypoints: ClassVar[list] = [
            Waypoint(
                location=Location(*location),
                time=BASE_TIME,
                instrument=[InstrumentType.ARGO_FLOAT],
            ),
        ]

        def _get_wps_in_use(self):
            return self.waypoints

    class DummyExpedition:
        schedule = DummySchedule()

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


def test_simulate_argo_floats_different_phases(tmpdir) -> None:
    """Handles multiple argo floats at different time steps, in differet phases."""
    lifetime_days = 1
    fieldset = create_fieldset(lifetime_days=lifetime_days)

    sensors = [
        SensorConfig(sensor_type=SensorType.TEMPERATURE),
        SensorConfig(sensor_type=SensorType.SALINITY),
    ]
    expedition = create_dummy_expedition(
        sensors, lifetime=timedelta(days=lifetime_days)
    )

    argo_instrument = ArgoFloatInstrument(expedition, None)

    # staggered deployments
    deploy_offsets = [timedelta(hours=0), timedelta(hours=2), timedelta(hours=4)]
    argo_floats = [
        create_argo_float(
            Waypoint(
                location=Location(latitude=2 + i, longitude=1 + i),
                time=BASE_TIME + offset,
                instrument=[InstrumentType.ARGO_FLOAT],
            )
        )
        for i, offset in enumerate(deploy_offsets)
    ]

    out_path = tmpdir.join("out_phases.parquet")
    argo_instrument.load_input_data = lambda: fieldset
    argo_instrument.simulate(argo_floats, out_path)

    results = parcels.read_particlefile(out_path)
    assert np.unique(results["particle_id"].to_numpy()).size == len(argo_floats)

    # every float should have sunk to and stayed at drift depth without overshooting
    for pid in np.unique(results["particle_id"].to_numpy()):
        z = results.filter(pl.col("particle_id") == pid)["z"].to_numpy()
        z = z[np.isfinite(z)]
        assert np.isclose(z.min(), DRIFT_DEPTH), (
            f"Float {pid} should reach drift depth without overshooting"
        )


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


def test_argo_float_reaches_max_depth_and_ascends(tmpdir) -> None:
    """Argo float should reach its max depth and then ascends."""
    lifetime_days = 1.0  # time enough for one descent to max depth + ascent
    fieldset = create_fieldset(
        lifetime_days=lifetime_days, depths=[-2225.1, -1941.9, -1000.0, -0.5]
    )

    sensors = [SensorConfig(sensor_type=SensorType.TEMPERATURE)]
    expedition = create_dummy_expedition(
        sensors, lifetime=timedelta(days=lifetime_days)
    )
    argo_instrument = ArgoFloatInstrument(expedition, None)
    wp = expedition.schedule.waypoints[0]
    argo_float = ArgoFloat(
        spacetime=Spacetime(location=wp.location, time=wp.time),
        min_depth=0.0,
        max_depth=MAX_DEPTH,
        drift_depth=DRIFT_DEPTH,
        vertical_speed=VERTICAL_SPEED,
        cycle_days=1,
        drift_days=0,
    )

    out_path = tmpdir.join("out.parquet")
    argo_instrument.load_input_data = lambda: fieldset
    argo_instrument.simulate([argo_float], out_path)

    results = parcels.read_particlefile(out_path)
    z = results["z"].to_numpy()
    phase = results["cycle_phase"].to_numpy()

    np.testing.assert_allclose(z.min(), MAX_DEPTH, atol=1e-3)
    assert not results["grounded"].to_numpy().any()

    # never sent back up early
    phase2_dz = np.diff(z)[(phase[:-1] == 2) & (phase[1:] == 2)]
    assert (phase2_dz <= 0).all()

    # ascent (sampling) starts from max depth
    assert np.isclose(z[phase == 3].min(), MAX_DEPTH, atol=1e-3)
    assert np.isfinite(results["temperature"].to_numpy()[phase == 3]).any()


def test_argo_max_depth_deeper_than_fieldset_error(tmpdir) -> None:
    """A max depth deeper than the fieldset depth is rejected at setup."""
    fieldset = create_fieldset(depths=[-1941.9, -1000.0, -0.5])

    sensors = [SensorConfig(sensor_type=SensorType.TEMPERATURE)]
    expedition = create_dummy_expedition(sensors)
    argo_instrument = ArgoFloatInstrument(expedition, None)
    argo_floats = [create_argo_float(wp) for wp in expedition.schedule.waypoints]

    argo_instrument.load_input_data = lambda: fieldset
    with pytest.raises(ValueError, match="deeper than the deepest level"):
        argo_instrument.simulate(argo_floats, tmpdir.join("out.parquet"))


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


def test_handle_grounding():
    """Test that _handle_grounding sets grounded status, logs warnings, adjusts dz, and updates cycle phase."""

    class DummyParticles:
        def __init__(self):
            self.grounded = np.array([0, 0])
            self.z = np.array([-1200.0, -1500.0])
            self.dz = np.array([0.0, 0.0])
            self.cycle_phase = np.array([1, 1])
            self.t = np.array([0.0, 0.0])
            self.y = np.array([10.0, 11.0])
            self.x = np.array([50.0, 51.0])

    ptcls = DummyParticles()

    # index 0 is grounded (-1000m bathymetry vs -1200m particle depth)
    # index 1 is safe (-2000m bathymetry vs -1500m particle depth)
    loc_bathy = np.array([-1000.0, -2000.0])
    bathysafe_mask = np.array([False, True])

    target_phase = 2
    fieldset = create_fieldset()

    # capture print outputs
    log_stream = io.StringIO()
    with contextlib.redirect_stdout(log_stream):
        _handle_grounding(
            ptcls_subset=ptcls,
            bathysafe_mask=bathysafe_mask,
            loc_bathy=loc_bathy,
            fieldset=fieldset,
            phase_name="descent",
            target_phase=target_phase,
        )

    output = log_stream.getvalue()

    # grounding mask applied correctly
    np.testing.assert_array_equal(ptcls.grounded, np.array([1, 0]))

    # dz updated (target depth = bathy + 50m = -1000 + 50 = -950m; dz = -950 - (-1200) = 250m)
    expected_dz = np.array([250.0, 0.0])
    np.testing.assert_allclose(ptcls.dz, expected_dz)

    # cycle phase updated
    np.testing.assert_array_equal(ptcls.cycle_phase, np.array([target_phase, 1]))

    # warning message printed
    assert (
        "Shallow bathymetry warning: Argo float grounded at bathymetry during descent"
        in output
    )


def test_keep_at_surface_no_infinite_loop(tmpdir):
    """_keep_at_surface kernel should not cause an infinite loop when particles are held at the surface after ErrorThroughSurface."""
    fieldset = create_fieldset(lifetime_days=1)
    pclass = parcels.Particle.add_variable(
        [
            parcels.Variable("min_depth", dtype=np.float32),
            parcels.Variable("n_evals", dtype=np.int32, initial=0),
        ]
    )

    # second float deployed after the first has been simulated for several output times
    pset = parcels.ParticleSet(
        fieldset=fieldset,
        pclass=pclass,
        x=[1.0, 1.0],
        y=[2.0, 2.0],
        z=[0.0, 0.0],
        t=[
            np.datetime64(BASE_TIME),
            np.datetime64(BASE_TIME + timedelta(hours=2)),
        ],
        min_depth=[0.0, 0.0],
    )

    # force every float through the surface
    # each float needs at most 36 steps of 5 minutes, so exceeding 100 evaluations means the kernel loop is stuck
    def _through_surface(particles, fieldset):
        particles.n_evals += 1
        if np.any(particles.n_evals > 100):
            raise RuntimeError("Infinite loop detected")
        particles.state[:] = parcels.StatusCode.ErrorThroughSurface

    out_file = parcels.ParticleFile(
        path=tmpdir.join("out_surface.parquet"), outputdt=timedelta(minutes=5)
    )
    endtime = np.datetime64(BASE_TIME + timedelta(hours=3))
    pset.execute(
        [_through_surface, _keep_at_surface],
        endtime=endtime,
        dt=timedelta(minutes=5),
        output_file=out_file,
    )

    # both floats reached endtime and were held at the surface
    np.testing.assert_array_equal(pset.t, [timedelta(hours=3).total_seconds()] * 2)
    np.testing.assert_array_equal(pset.z, [0.0, 0.0])


def test_argo_no_initial_sampling(tmpdir):
    """Test that ArgoFloat does not sample at initial deployment (on purpose for realism)."""
    fieldset = create_fieldset()

    sensors = [
        SensorConfig(sensor_type=SensorType.TEMPERATURE),
        SensorConfig(sensor_type=SensorType.SALINITY),
    ]
    expedition = create_dummy_expedition(sensors)

    argo_instrument = ArgoFloatInstrument(expedition, None)
    argo_floats = [create_argo_float(wp) for wp in expedition.schedule.waypoints]
    out_path = tmpdir.join("out_no_initial.parquet")
    argo_instrument.load_input_data = lambda: fieldset
    argo_instrument.simulate(argo_floats, out_path)

    results = parcels.read_particlefile(out_path)

    # check no sampling occured at initial deployment
    deploy_time = fieldset.time_interval.left
    initial = results.filter(pl.col("t") == deploy_time)
    assert len(initial) == 1, "Should only be one entry for initial deployment time"
    assert initial["temperature"].is_nan().all(), (
        "ArgoFloat should not sample temperature at initial deployment"
    )
    assert initial["salinity"].is_nan().all(), (
        "ArgoFloat should not sample salinity at initial deployment"
    )
