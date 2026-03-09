"""Test the simulation of drifters."""

import datetime
from typing import ClassVar

import numpy as np
import xarray as xr

from parcels import FieldSet
from virtualship.instruments.drifter import Drifter, DrifterInstrument
from virtualship.models import Location, Spacetime
from virtualship.models.expedition import Waypoint

BASE_TIME = datetime.datetime.strptime("1950-01-01", "%Y-%m-%d")
LIFETIME = datetime.timedelta(days=1)

DEPLOY_DEPTH = -1.0  # default


def create_dummy_expedition():
    # arbitrary time offset for the dummy fieldset

    class DummyExpedition:
        class schedule:
            waypoints: ClassVar = [
                Waypoint(
                    location=Location(
                        1, 2
                    ),  # any location is fine for dummy, actual drifter deployment locations are defined in the test functions
                    time=BASE_TIME,
                ),
            ]

        class instruments_config:
            class drifter_config:
                lifetime = LIFETIME
                depth_meter = DEPLOY_DEPTH

    return DummyExpedition()


def test_simulate_drifters(tmpdir) -> None:
    CONST_TEMPERATURE = 1.0  # constant temperature in fieldset

    v = np.full((2, 2, 2), 1.0)
    u = np.full((2, 2, 2), 1.0)
    t = np.full((2, 2, 2), CONST_TEMPERATURE)

    fieldset = FieldSet.from_data(
        {"V": v, "U": u, "T": t},
        {
            "lon": np.array([0.0, 10.0]),
            "lat": np.array([0.0, 10.0]),
            "time": [
                np.datetime64(BASE_TIME + datetime.timedelta(seconds=0)),
                np.datetime64(BASE_TIME + datetime.timedelta(days=3)),
            ],
        },
    )

    # drifters to deploy
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
    out_path = tmpdir.join("out.zarr")

    drifter_instrument.load_input_data = lambda: fieldset
    drifter_instrument.simulate(drifters, out_path)

    # test if output is as expected
    results = xr.open_zarr(out_path)

    assert len(results.trajectory) == len(drifters)

    for drifter_i, traj in enumerate(results.trajectory):
        # Check if drifters are moving
        # lat, lon, should be increasing values (with the above positive VU fieldset)
        dlat = np.diff(results.sel(trajectory=traj)["lat"].values)
        assert np.all(dlat[np.isfinite(dlat)] > 0), (
            f"Drifter is not moving over y {drifter_i=}"
        )
        dlon = np.diff(results.sel(trajectory=traj)["lon"].values)
        assert np.all(dlon[np.isfinite(dlon)] > 0), (
            f"Drifter is not moving over x {drifter_i=}"
        )
        temp = results.sel(trajectory=traj)["temperature"].values
        assert np.all(temp[np.isfinite(temp)] == CONST_TEMPERATURE), (
            f"measured temperature does not match {drifter_i=}"
        )


def test_drifter_depths(tmpdir) -> None:
    CONST_TEMPERATURE = 1.0  # constant temperature in fieldset

    v = np.full((2, 2, 2, 2), 1.0)
    u = np.full((2, 2, 2, 2), 1.0)
    t = np.full((2, 2, 2, 2), CONST_TEMPERATURE)

    # different values at depth (random)
    v[:, -1, :, :] = 1.0 * np.random.randint(0, 10)
    u[:, -1, :, :] = 1.0 * np.random.randint(0, 10)
    t[:, -1, :, :] = CONST_TEMPERATURE * np.random.randint(0, 10)

    fieldset = FieldSet.from_data(
        {"V": v, "U": u, "T": t},
        {
            "time": [
                np.datetime64(BASE_TIME + datetime.timedelta(seconds=0)),
                np.datetime64(BASE_TIME + datetime.timedelta(days=3)),
            ],
            "depth": np.array([-10, 0]),
            "lat": np.array([0.0, 10.0]),
            "lon": np.array([0.0, 10.0]),
        },
    )

    # drifters to deploy (same time and location, but different depths)
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
            depth=DEPLOY_DEPTH - 5.0,  # different drogue depth
            lifetime=datetime.timedelta(hours=12),
        ),
    ]

    expedition = create_dummy_expedition()
    from_data = None

    drifter_instrument = DrifterInstrument(expedition, from_data)
    out_path = tmpdir.join("out.zarr")

    drifter_instrument.load_input_data = lambda: fieldset
    drifter_instrument.simulate(drifters, out_path)

    # test if output is as expected
    results = xr.open_zarr(out_path)

    assert len(results.trajectory) == len(drifters)

    drifter_surface = results.isel(trajectory=0)
    drifter_depth = results.isel(trajectory=1)

    assert drifter_surface.z[0] > drifter_depth.z[0], (
        "Surface drifter should be at shallower depth than deeper drifter"
    )

    surface_depths = drifter_surface.z.values
    depth_depths = drifter_depth.z.values
    assert np.all(surface_depths[~np.isnan(surface_depths)] == surface_depths[0]), (
        "Surface drifter depth should be constant"
    )
    assert np.all(depth_depths[~np.isnan(depth_depths)] == depth_depths[0]), (
        "Depth drifter depth should be constant"
    )

    assert drifter_surface.temperature[0] != drifter_depth.temperature[0], (
        "Surface and deeper drifter should have different temperature measurements"
    )
