"""Test the simulation of drifters."""

import datetime

import numpy as np
import xarray as xr
from parcels import FieldSet, Field, VectorField, XGrid

from virtualship.instruments.drifter import Drifter, simulate_drifters
from virtualship.models import Location, Spacetime


def test_simulate_drifters(tmpdir) -> None:
    # arbitrary time offset for the dummy fieldset
    base_time = np.datetime64("1950-01-01")

    CONST_TEMPERATURE = 1.0  # constant temperature in fieldset

    dims = (2, 2, 2)  # time, lat, lon
    v = np.full(dims, 1.0)
    u = np.full(dims, 1.0)
    t = np.full(dims, CONST_TEMPERATURE)

    time = [base_time, base_time + np.timedelta64(3, "D")]
    ds = xr.Dataset(
        {"U": (["time", "YG", "XG"], u), "V": (["time", "YG", "XG"], v), "T": (["time", "YG", "XG"], t)},
        coords={
            "time": (["time"], time, {"axis": "T"}),
            "YC": (["YC"], np.arange(dims[1]) + 0.5, {"axis": "Y"}),
            "YG": (["YG"], np.arange(dims[1]), {"axis": "Y", "c_grid_axis_shift": -0.5}),
            "XC": (["XC"], np.arange(dims[2]) + 0.5, {"axis": "X"}),
            "XG": (["XG"], np.arange(dims[2]), {"axis": "X", "c_grid_axis_shift": -0.5}),
            "lat": (["YG"], np.linspace(-10, 10, dims[1]), {"axis": "Y", "c_grid_axis_shift": 0.5}),
            "lon": (["XG"], np.linspace(-10, 10, dims[2]), {"axis": "X", "c_grid_axis_shift": -0.5}),
        },
    )

    grid = XGrid.from_dataset(ds, mesh="spherical")
    U = Field("U", ds["U"], grid)
    V = Field("V", ds["V"], grid)
    T = Field("T", ds["T"], grid)
    UV = VectorField("UV", U, V)
    fieldset = FieldSet([U, V, T, UV])


    # drifters to deploy
    drifters = [
        Drifter(
            spacetime=Spacetime(
                location=Location(latitude=0, longitude=0),
                time=base_time + np.timedelta64(0, "D"),
            ),
            depth=0.0,
            lifetime=np.timedelta64(2, "h"),
        ),
        Drifter(
            spacetime=Spacetime(
                location=Location(latitude=1, longitude=1),
                time=base_time + np.timedelta64(20, "h"),
            ),
            depth=0.0,
            lifetime=None,
        ),
    ]

    # perform simulation
    out_path = tmpdir.join("out.zarr")

    simulate_drifters(
        fieldset=fieldset,
        out_path=out_path,
        drifters=drifters,
        outputdt=datetime.timedelta(hours=1),
        dt=datetime.timedelta(minutes=5),
        endtime=None,
    )

    # test if output is as expected
    results = xr.open_zarr(out_path, decode_cf=False)  # TODO fix decode_cf when parcels v4 is fixed

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
