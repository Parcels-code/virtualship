"""Test the simulation of drifters."""

import datetime

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

    class DummyExpedition:
        class schedule:
            waypoints: list[Waypoint] = [  # noqa: RUF012
                Waypoint(location=Location(*location), time=BASE_TIME)
            ]

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
