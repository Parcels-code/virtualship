"""Test the simulation of drifters."""

import datetime
from typing import ClassVar

import numpy as np
import parcels
import polars as pl
import pydantic
import pytest
import xarray as xr

from virtualship.instruments.drifter import Drifter, DrifterInstrument
from virtualship.instruments.sensors import SensorType
from virtualship.instruments.types import InstrumentType
from virtualship.models import Location, Spacetime
from virtualship.models.expedition import (
    DrifterConfig,
    InstrumentsConfig,
    SensorConfig,
    Waypoint,
)

BASE_TIME = datetime.datetime.strptime("1950-01-01", "%Y-%m-%d")
LIFETIME = datetime.timedelta(days=1)
DEPLOY_DEPTH = -1.0


def create_dummy_expedition(
    sensors=None,
    lifetime=LIFETIME,
    depth=DEPLOY_DEPTH,
    location=(1, 2),
):
    if sensors is None:
        sensors = [SensorConfig(sensor_type=SensorType.TEMPERATURE)]

    class DummySchedule:
        waypoints: ClassVar[list] = [
            Waypoint(
                location=Location(*location),
                time=BASE_TIME,
                instrument=[InstrumentType.DRIFTER],
            ),
        ]

        def _get_wps_in_use(self):
            return self.waypoints

    class DummyExpedition:
        schedule = DummySchedule()

        instruments_config = InstrumentsConfig(
            drifter_config=DrifterConfig(
                lifetime=lifetime,
                depth_meter=depth,
                stationkeeping_time_minutes=10,
                sensors=sensors,
            )
        )

    return DummyExpedition()


def create_fieldset(
    data_dict,
    lon_range=(0.0, 10.0),
    lat_range=(0.0, 10.0),
    depth_range=None,
    time_range=None,
):
    if time_range is None:
        time_range = [
            np.datetime64(BASE_TIME),
            np.datetime64(BASE_TIME + datetime.timedelta(days=3)),
        ]

    data_vars = {}
    is_3d = depth_range is not None

    for key, val in data_dict.items():
        if is_3d:
            data_vars[key] = (("time", "depth", "lat", "lon"), val)
        else:
            data_vars[key] = (("time", "lat", "lon"), val)

    coords = {
        "lon": (("lon"), np.array(lon_range), {"units": "degrees_east"}),
        "lat": (("lat"), np.array(lat_range), {"units": "degrees_north"}),
        "time": (("time"), time_range, {"axis": "T"}),
    }
    if is_3d:
        coords["depth"] = (("depth"), np.array(depth_range))

    ds_fields = xr.Dataset(data_vars=data_vars, coords=coords)

    fields = {var: ds_fields[var] for var in data_vars.keys()}
    ds_fset = parcels.convert.copernicusmarine_to_sgrid(fields=fields)
    fieldset = parcels.FieldSet.from_sgrid_conventions(ds_fset)

    return fieldset


def test_simulate_drifters(tmpdir) -> None:
    CONST_TEMPERATURE = 1.0  # constant temperature in fieldset

    v = np.full((2, 2, 2), 1.0)
    u = np.full((2, 2, 2), 1.0)
    t = np.full((2, 2, 2), CONST_TEMPERATURE)

    fieldset = create_fieldset({"V": v, "U": u, "T": t})

    drifters = [
        Drifter(
            spacetime=Spacetime(
                location=Location(latitude=0.5, longitude=0.5),
                time=BASE_TIME + datetime.timedelta(days=0),
            ),
            depth=DEPLOY_DEPTH,
            lifetime=datetime.timedelta(hours=2),
        ),
        Drifter(
            spacetime=Spacetime(
                location=Location(latitude=1, longitude=1),
                time=BASE_TIME + datetime.timedelta(hours=20),
            ),
            depth=DEPLOY_DEPTH,
            lifetime=None,
        ),
    ]

    expedition = create_dummy_expedition()
    from_data = None

    drifter_instrument = DrifterInstrument(expedition, from_data)
    out_path = tmpdir.join("out.parquet")

    drifter_instrument.load_input_data = lambda: fieldset
    drifter_instrument.simulate(drifters, out_path)

    results = parcels.read_particlefile(out_path)

    assert np.unique(results["particle_id"].to_numpy()).size == len(drifters)

    for drifter_i, traj_id in enumerate(np.unique(results["particle_id"].to_numpy())):
        traj_df = results.filter(pl.col("particle_id") == traj_id)

        dlat = np.diff(traj_df["y"].to_numpy())
        assert np.all(dlat[np.isfinite(dlat)] > 0), (
            f"Drifter is not moving over y {drifter_i=}"
        )

        dlon = np.diff(traj_df["x"].to_numpy())
        assert np.all(dlon[np.isfinite(dlon)] > 0), (
            f"Drifter is not moving over x {drifter_i=}"
        )

        temp = traj_df["temperature"].to_numpy()
        assert np.all(temp[np.isfinite(temp)] == CONST_TEMPERATURE), (
            f"measured temperature does not match {drifter_i=}"
        )


def test_simulate_drifters_multiple_waypoints(tmpdir) -> None:
    """Should handle multiple drifters deployed at different waypoints and times."""
    fieldset = create_fieldset(
        {
            "V": np.full((2, 2, 2), 1.0),
            "U": np.full((2, 2, 2), 1.0),
            "T": np.full((2, 2, 2), 1.0),
        }
    )

    # all drifters share the single lifetime from the expedition's drifter config
    expedition = create_dummy_expedition(lifetime=datetime.timedelta(hours=12))
    lifetime = expedition.instruments_config.drifter_config.lifetime

    # staggered deployments (at multiples of the 5h output interval), so the first drifter
    # reaches the end of its lifetime whilst others are still drifting
    waypoints = [
        (Location(latitude=1.0, longitude=1.0), datetime.timedelta(hours=0)),
        (Location(latitude=2.0, longitude=2.0), datetime.timedelta(hours=5)),
        (Location(latitude=3.0, longitude=3.0), datetime.timedelta(hours=10)),
    ]
    drifters = [
        Drifter(
            spacetime=Spacetime(location=location, time=BASE_TIME + offset),
            depth=DEPLOY_DEPTH,
            lifetime=lifetime,
        )
        for location, offset in waypoints
    ]

    drifter_instrument = DrifterInstrument(expedition, None)
    out_path = tmpdir.join("out_multiple.parquet")
    drifter_instrument.load_input_data = lambda: fieldset
    drifter_instrument.simulate(drifters, out_path)

    results = parcels.read_particlefile(out_path)
    pids = np.unique(results["particle_id"].to_numpy())
    assert pids.size == len(drifters)

    last_times = []
    for drifter, pid in zip(drifters, pids, strict=True):
        drifter_df = results.filter(pl.col("particle_id") == pid).drop_nulls("t")
        first = drifter_df.sort("t")[0]
        last_times.append(drifter_df["t"].max())

        assert first["t"].item() == drifter.spacetime.time, (
            f"Drifter {pid} should start at its deployment time"
        )
        assert np.isclose(first["y"].item(), drifter.spacetime.location.lat, atol=0.1)
        assert np.isclose(first["x"].item(), drifter.spacetime.location.lon, atol=0.1)

        assert last_times[-1] <= drifter.spacetime.time + lifetime, (
            f"Drifter {pid} should stop at the end of its lifetime"
        )

    assert last_times == sorted(last_times) and len(set(last_times)) == len(
        last_times
    ), "With a shared lifetime, later-deployed drifters should stop later"


def test_simulate_drifters_at_same_waypoint(tmpdir) -> None:
    """Multiple drifters deployed at the same waypoint (same location, time and depth) are simulated as separate drifters."""
    fieldset = create_fieldset(
        {
            "V": np.full((2, 2, 2), 1.0),
            "U": np.full((2, 2, 2), 1.0),
            "T": np.full((2, 2, 2), 1.0),
        }
    )

    expedition = create_dummy_expedition()

    n_drifters = 3
    drifters = [
        Drifter(
            spacetime=Spacetime(
                location=Location(latitude=1.0, longitude=1.0),
                time=BASE_TIME,
            ),
            depth=DEPLOY_DEPTH,
            lifetime=expedition.instruments_config.drifter_config.lifetime,
        )
        for _ in range(n_drifters)
    ]

    drifter_instrument = DrifterInstrument(expedition, None)
    out_path = tmpdir.join("out_same_waypoint.parquet")
    drifter_instrument.load_input_data = lambda: fieldset
    drifter_instrument.simulate(drifters, out_path)

    results = parcels.read_particlefile(out_path)
    pids = np.unique(results["particle_id"].to_numpy())
    assert pids.size == n_drifters

    # small random noise is added to release locations, so drifters at the same waypoint follow different trajectories
    release_points = set()
    for pid in pids:
        first = results.filter(pl.col("particle_id") == pid).sort("t")[0]
        assert np.isclose(first["y"].item(), 1.0, atol=0.1)
        assert np.isclose(first["x"].item(), 1.0, atol=0.1)
        release_points.add((first["y"].item(), first["x"].item()))
    assert len(release_points) == n_drifters, (
        "Drifters at the same waypoint should have distinct release locations"
    )


def test_drifter_depths(tmpdir) -> None:
    CONST_TEMPERATURE = 1.0  # constant temperature in fieldset
    DEPTH_FACTOR = 3.0  # factor to multiply surface values by at depth for test

    v = np.full((2, 2, 2, 2), 1.0)
    u = np.full((2, 2, 2, 2), 1.0)
    t = np.full((2, 2, 2, 2), CONST_TEMPERATURE)

    v[:, -1, :, :] = 1.0 * DEPTH_FACTOR
    u[:, -1, :, :] = 1.0 * DEPTH_FACTOR
    t[:, -1, :, :] = CONST_TEMPERATURE * DEPTH_FACTOR

    fieldset = create_fieldset(
        {"V": v, "U": u, "T": t},
        depth_range=(-10, 0),
    )

    drifters = [
        Drifter(
            spacetime=Spacetime(
                location=Location(latitude=5.0, longitude=5.0),
                time=BASE_TIME + datetime.timedelta(days=0),
            ),
            depth=DEPLOY_DEPTH,
            lifetime=datetime.timedelta(hours=12),
        ),
        Drifter(
            spacetime=Spacetime(
                location=Location(latitude=5.0, longitude=5.0),
                time=BASE_TIME + datetime.timedelta(days=0),
            ),
            depth=DEPLOY_DEPTH - 5.0,
            lifetime=datetime.timedelta(hours=12),
        ),
    ]

    expedition = create_dummy_expedition()
    from_data = None

    drifter_instrument = DrifterInstrument(expedition, from_data)
    out_path = tmpdir.join("out.parquet")

    drifter_instrument.load_input_data = lambda: fieldset
    drifter_instrument.simulate(drifters, out_path)

    results = parcels.read_particlefile(out_path)

    pids = np.unique(results["particle_id"].to_numpy())
    assert pids.size == len(drifters)

    drifter_surface = results.filter(pl.col("particle_id") == pids[0])
    drifter_depth = results.filter(pl.col("particle_id") == pids[1])

    assert drifter_surface["z"][0] > drifter_depth["z"][0], (
        "Surface drifter should be at shallower depth than deeper drifter"
    )

    surface_depths = drifter_surface["z"].to_numpy()
    depth_depths = drifter_depth["z"].to_numpy()
    assert np.all(surface_depths[~np.isnan(surface_depths)] == surface_depths[0]), (
        "Surface drifter depth should be constant"
    )
    assert np.all(depth_depths[~np.isnan(depth_depths)] == depth_depths[0]), (
        "Depth drifter depth should be constant"
    )

    assert drifter_surface["temperature"][0] != drifter_depth["temperature"][0], (
        "Surface and deeper drifter should have different temperature measurements"
    )


def test_drifter_disabled_sensor_absent_from_output(tmpdir) -> None:
    """A DrifterConfig with no enabled sensors should be rejected at construction time."""
    with pytest.raises(pydantic.ValidationError, match="no enabled sensors"):
        DrifterConfig(
            lifetime=LIFETIME,
            depth_meter=DEPLOY_DEPTH,
            stationkeeping_time_minutes=10,
            sensors=[],
        )


def test_drifter_config_default_sensors():
    """DrifterConfig defaults to TEMPERATURE."""
    config = DrifterConfig(
        lifetime=LIFETIME,
        depth_meter=DEPLOY_DEPTH,
        stationkeeping_time_minutes=10,
    )
    assert config.sensors[0].sensor_type is SensorType.TEMPERATURE


def test_drifter_config_unsupported_sensor_rejected():
    """Unsupported sensor on Drifter is rejected."""
    with pytest.raises(pydantic.ValidationError, match="does not support"):
        DrifterConfig(
            lifetime=LIFETIME,
            depth_meter=DEPLOY_DEPTH,
            stationkeeping_time_minutes=10,
            sensors=[SensorConfig(sensor_type=SensorType.VELOCITY)],
        )


def test_drifter_instrument_type():
    """DrifterInstrument returns the correct InstrumentType and if is underway instrument."""
    expedition = create_dummy_expedition()

    drifter_instrument = DrifterInstrument(expedition, from_data=None)
    assert drifter_instrument.instrument_type == InstrumentType.DRIFTER
    assert not drifter_instrument.instrument_type.is_underway
