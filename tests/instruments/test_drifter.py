"""Test the simulation of drifters."""

import datetime

import numpy as np
import xarray as xr
from parcels import FieldSet

from virtualship.instruments.drifter import Drifter, simulate_drifters
from virtualship.models import Location, Spacetime


def test_simulate_drifters(tmpdir) -> None:
    # arbitrary time offset for the dummy fieldset
    base_time = datetime.datetime.strptime("1950-01-01", "%Y-%m-%d")

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
                np.datetime64(base_time + datetime.timedelta(seconds=0)),
                np.datetime64(base_time + datetime.timedelta(days=3)),
            ],
        },
    )

    # drifters to deploy
    drifters = [
        Drifter(
            spacetime=Spacetime(
                location=Location(latitude=0, longitude=0),
                time=base_time + datetime.timedelta(days=0),
            ),
            depth=0.0,
            lifetime=datetime.timedelta(hours=2),
        ),
        Drifter(
            spacetime=Spacetime(
                location=Location(latitude=1, longitude=1),
                time=base_time + datetime.timedelta(hours=20),
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
