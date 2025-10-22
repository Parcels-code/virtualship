"""
Test the simulation of CTD instruments.

Fields are kept static over time and time component of CTD measurements is not tested tested because it's tricky to provide expected measurements.
"""

import datetime
from datetime import timedelta

import numpy as np
import pytest
import xarray as xr
from parcels import Field, FieldSet, VectorField, XGrid

from virtualship.instruments.ctd import CTD, simulate_ctd
from virtualship.models import Location, Spacetime


def test_simulate_ctds(tmpdir) -> None:
    # arbitrary time offset for the dummy fieldset
    base_time = np.datetime64("1950-01-01")

    # where to cast CTDs
    ctds = [
        CTD(
            spacetime=Spacetime(
                location=Location(latitude=0, longitude=1),
                time=base_time + np.timedelta64(0, "h"),
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
    dims = (2, 2, 2, 2)  # time, depth, lat, lon
    u = np.zeros(dims)
    v = np.zeros(dims)
    t = np.zeros(dims)
    s = np.zeros(dims)
    b = -1000 * np.ones(dims)

    t[:, 1, 0, 1] = ctd_exp[0]["surface"]["temperature"]
    t[:, 0, 0, 1] = ctd_exp[0]["maxdepth"]["temperature"]
    t[:, 1, 1, 0] = ctd_exp[1]["surface"]["temperature"]
    t[:, 0, 1, 0] = ctd_exp[1]["maxdepth"]["temperature"]

    s[:, 1, 0, 1] = ctd_exp[0]["surface"]["salinity"]
    s[:, 0, 0, 1] = ctd_exp[0]["maxdepth"]["salinity"]
    s[:, 1, 1, 0] = ctd_exp[1]["surface"]["salinity"]
    s[:, 0, 1, 0] = ctd_exp[1]["maxdepth"]["salinity"]


    lons, lats = np.linspace(-1, 2, dims[2]), np.linspace(-1, 2, dims[3])  # TODO set to (0, 1) once Parcels can interpolate on domain boundaries
    ds = xr.Dataset(
        {
            "U": (["time", "depth", "YG", "XG"], u),
            "V": (["time", "depth", "YG", "XG"], v),
            "T": (["time", "depth", "YG", "XG"], t),
            "S": (["time", "depth", "YG", "XG"], s),
            "bathymetry": (["time", "depth", "YG", "XG"], b),
        },
        coords={
            "time": (["time"], [base_time, base_time + np.timedelta64(1, "h")], {"axis": "T"}),
            "depth": (["depth"], np.linspace(-1000, 0, dims[1]), {"axis": "Z"}),
            "YC": (["YC"], np.arange(dims[2]) + 0.5, {"axis": "Y"}),
            "YG": (["YG"], np.arange(dims[2]), {"axis": "Y", "c_grid_axis_shift": -0.5}),
            "XC": (["XC"], np.arange(dims[3]) + 0.5, {"axis": "X"}),
            "XG": (["XG"], np.arange(dims[3]), {"axis": "X", "c_grid_axis_shift": -0.5}),
            "lat": (["YG"], lats, {"axis": "Y", "c_grid_axis_shift": 0.5}),
            "lon": (["XG"], lons, {"axis": "X", "c_grid_axis_shift": -0.5}),
        },
    )

    grid = XGrid.from_dataset(ds, mesh="spherical")
    U = Field("U", ds["U"], grid)
    V = Field("V", ds["V"], grid)
    T = Field("T", ds["T"], grid)
    S = Field("S", ds["S"], grid)
    B = Field("bathymetry", ds["bathymetry"], grid)
    UV = VectorField("UV", U, V)
    fieldset = FieldSet([U, V, S, T, B, UV])

    # perform simulation
    out_path = tmpdir.join("out.zarr")

    simulate_ctd(
        ctds=ctds,
        fieldset=fieldset,
        out_path=out_path,
        outputdt=timedelta(seconds=10),
    )

    # test if output is as expected
    results = xr.open_zarr(out_path)

    assert len(results.trajectory) == len(ctds)
    assert (np.min(results.z) == -1000.0)

    pytest.skip(reason="Parcels v4 can't interpolate on grid boundaries, leading to NaN values in output.")
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
