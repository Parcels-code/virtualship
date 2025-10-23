"""
Test the simulation of CTD_BGC instruments.

Fields are kept static over time and time component of CTD_BGC measurements is not tested because it's tricky to provide expected measurements.
"""

import datetime
from datetime import timedelta

import numpy as np
import pytest
import xarray as xr
from parcels import Field, FieldSet, VectorField, XGrid

from virtualship.instruments.ctd_bgc import CTD_BGC, simulate_ctd_bgc
from virtualship.models import Location, Spacetime


def test_simulate_ctd_bgcs(tmpdir) -> None:
    # arbitrary time offset for the dummy fieldset
    base_time = np.datetime64("1950-01-01")

    # where to cast CTD_BGCs
    ctd_bgcs = [
        CTD_BGC(
            spacetime=Spacetime(
                location=Location(latitude=0, longitude=1),
                time=base_time + datetime.timedelta(hours=0),
            ),
            min_depth=0,
            max_depth=float("-inf"),
        ),
        CTD_BGC(
            spacetime=Spacetime(
                location=Location(latitude=1, longitude=0),
                time=base_time,
            ),
            min_depth=0,
            max_depth=float("-inf"),
        ),
    ]

    # expected observations for ctd_bgcs at surface and at maximum depth
    ctd_bgc_exp = [
        {
            "surface": {
                "o2": 9,
                "chl": 10,
                "no3": 13,
                "po4": 14,
                "ph": 8.1,
                "phyc": 15,
                "zooc": 16,
                "nppv": 17,
                "lat": ctd_bgcs[0].spacetime.location.lat,
                "lon": ctd_bgcs[0].spacetime.location.lon,
            },
            "maxdepth": {
                "o2": 11,
                "chl": 12,
                "no3": 18,
                "po4": 19,
                "ph": 8.0,
                "phyc": 20,
                "zooc": 21,
                "nppv": 22,
                "lat": ctd_bgcs[0].spacetime.location.lat,
                "lon": ctd_bgcs[0].spacetime.location.lon,
            },
        },
        {
            "surface": {
                "o2": 9,
                "chl": 10,
                "no3": 13,
                "po4": 14,
                "ph": 8.1,
                "phyc": 15,
                "zooc": 16,
                "nppv": 17,
                "lat": ctd_bgcs[1].spacetime.location.lat,
                "lon": ctd_bgcs[1].spacetime.location.lon,
            },
            "maxdepth": {
                "o2": 11,
                "chl": 12,
                "no3": 18,
                "po4": 19,
                "ph": 8.0,
                "phyc": 20,
                "zooc": 21,
                "nppv": 22,
                "lat": ctd_bgcs[1].spacetime.location.lat,
                "lon": ctd_bgcs[1].spacetime.location.lon,
            },
        },
    ]

    # create fieldset based on the expected observations
    # indices are time, depth, latitude, longitude
    dims = (2, 2, 2, 2)  # time, depth, lat, lon
    u = np.zeros(dims)
    v = np.zeros(dims)
    o2 = np.zeros(dims)
    chl = np.zeros(dims)
    no3 = np.zeros(dims)
    po4 = np.zeros(dims)
    ph = np.zeros(dims)
    phyc = np.zeros(dims)
    zooc = np.zeros(dims)
    nppv = np.zeros(dims)
    b = -1000 * np.ones(dims)

    # Fill fields for both CTDs at surface and maxdepth
    o2[:, 1, 0, 1] = ctd_bgc_exp[0]["surface"]["o2"]
    o2[:, 0, 0, 1] = ctd_bgc_exp[0]["maxdepth"]["o2"]
    o2[:, 1, 1, 0] = ctd_bgc_exp[1]["surface"]["o2"]
    o2[:, 0, 1, 0] = ctd_bgc_exp[1]["maxdepth"]["o2"]

    chl[:, 1, 0, 1] = ctd_bgc_exp[0]["surface"]["chl"]
    chl[:, 0, 0, 1] = ctd_bgc_exp[0]["maxdepth"]["chl"]
    chl[:, 1, 1, 0] = ctd_bgc_exp[1]["surface"]["chl"]
    chl[:, 0, 1, 0] = ctd_bgc_exp[1]["maxdepth"]["chl"]

    no3[:, 1, 0, 1] = ctd_bgc_exp[0]["surface"]["no3"]
    no3[:, 0, 0, 1] = ctd_bgc_exp[0]["maxdepth"]["no3"]
    no3[:, 1, 1, 0] = ctd_bgc_exp[1]["surface"]["no3"]
    no3[:, 0, 1, 0] = ctd_bgc_exp[1]["maxdepth"]["no3"]

    po4[:, 1, 0, 1] = ctd_bgc_exp[0]["surface"]["po4"]
    po4[:, 0, 0, 1] = ctd_bgc_exp[0]["maxdepth"]["po4"]
    po4[:, 1, 1, 0] = ctd_bgc_exp[1]["surface"]["po4"]
    po4[:, 0, 1, 0] = ctd_bgc_exp[1]["maxdepth"]["po4"]

    ph[:, 1, 0, 1] = ctd_bgc_exp[0]["surface"]["ph"]
    ph[:, 0, 0, 1] = ctd_bgc_exp[0]["maxdepth"]["ph"]
    ph[:, 1, 1, 0] = ctd_bgc_exp[1]["surface"]["ph"]
    ph[:, 0, 1, 0] = ctd_bgc_exp[1]["maxdepth"]["ph"]

    phyc[:, 1, 0, 1] = ctd_bgc_exp[0]["surface"]["phyc"]
    phyc[:, 0, 0, 1] = ctd_bgc_exp[0]["maxdepth"]["phyc"]
    phyc[:, 1, 1, 0] = ctd_bgc_exp[1]["surface"]["phyc"]
    phyc[:, 0, 1, 0] = ctd_bgc_exp[1]["maxdepth"]["phyc"]

    zooc[:, 1, 0, 1] = ctd_bgc_exp[0]["surface"]["zooc"]
    zooc[:, 0, 0, 1] = ctd_bgc_exp[0]["maxdepth"]["zooc"]
    zooc[:, 1, 1, 0] = ctd_bgc_exp[1]["surface"]["zooc"]
    zooc[:, 0, 1, 0] = ctd_bgc_exp[1]["maxdepth"]["zooc"]

    nppv[:, 1, 0, 1] = ctd_bgc_exp[0]["surface"]["nppv"]
    nppv[:, 0, 0, 1] = ctd_bgc_exp[0]["maxdepth"]["nppv"]
    nppv[:, 1, 1, 0] = ctd_bgc_exp[1]["surface"]["nppv"]
    nppv[:, 0, 1, 0] = ctd_bgc_exp[1]["maxdepth"]["nppv"]

    lons, lats = (
        np.linspace(-1, 2, dims[2]),
        np.linspace(-1, 2, dims[3]),
    )  # TODO set to (0, 1) once Parcels can interpolate on domain boundaries
    ds = xr.Dataset(
        {
            "U": (["time", "depth", "YG", "XG"], u),
            "V": (["time", "depth", "YG", "XG"], v),
            "o2": (["time", "depth", "YG", "XG"], o2),
            "chl": (["time", "depth", "YG", "XG"], chl),
            "no3": (["time", "depth", "YG", "XG"], no3),
            "po4": (["time", "depth", "YG", "XG"], po4),
            "ph": (["time", "depth", "YG", "XG"], ph),
            "phyc": (["time", "depth", "YG", "XG"], phyc),
            "zooc": (["time", "depth", "YG", "XG"], zooc),
            "nppv": (["time", "depth", "YG", "XG"], nppv),
            "bathymetry": (["time", "depth", "YG", "XG"], b),
        },
        coords={
            "time": (
                ["time"],
                [base_time, base_time + np.timedelta64(1, "h")],
                {"axis": "T"},
            ),
            "depth": (["depth"], np.linspace(-1000, 0, dims[1]), {"axis": "Z"}),
            "YC": (["YC"], np.arange(dims[2]) + 0.5, {"axis": "Y"}),
            "YG": (
                ["YG"],
                np.arange(dims[2]),
                {"axis": "Y", "c_grid_axis_shift": -0.5},
            ),
            "XC": (["XC"], np.arange(dims[3]) + 0.5, {"axis": "X"}),
            "XG": (
                ["XG"],
                np.arange(dims[3]),
                {"axis": "X", "c_grid_axis_shift": -0.5},
            ),
            "lat": (["YG"], lats, {"axis": "Y", "c_grid_axis_shift": 0.5}),
            "lon": (["XG"], lons, {"axis": "X", "c_grid_axis_shift": -0.5}),
        },
    )

    grid = XGrid.from_dataset(ds, mesh="spherical")
    U = Field("U", ds["U"], grid)
    V = Field("V", ds["V"], grid)
    o2 = Field("o2", ds["o2"], grid)
    chl = Field("chl", ds["chl"], grid)
    no3 = Field("no3", ds["no3"], grid)
    po4 = Field("po4", ds["po4"], grid)
    ph = Field("ph", ds["ph"], grid)
    phyc = Field("phyc", ds["phyc"], grid)
    zooc = Field("zooc", ds["zooc"], grid)
    nppv = Field("nppv", ds["nppv"], grid)
    B = Field("bathymetry", ds["bathymetry"], grid)
    UV = VectorField("UV", U, V)
    fieldset = FieldSet([U, V, o2, chl, no3, po4, ph, phyc, zooc, nppv, B, UV])

    # perform simulation
    out_path = tmpdir.join("out.zarr")

    simulate_ctd_bgc(
        ctd_bgcs=ctd_bgcs,
        fieldset=fieldset,
        out_path=out_path,
        outputdt=timedelta(seconds=10),
    )

    # test if output is as expected
    results = xr.open_zarr(out_path)

    assert len(results.trajectory) == len(ctd_bgcs)
    assert np.min(results.z) == -1000.0

    pytest.skip(
        reason="Parcels v4 can't interpolate on grid boundaries, leading to NaN values in output."
    )

    for ctd_i, (traj, exp_bothloc) in enumerate(
        zip(results.trajectory, ctd_bgc_exp, strict=True)
    ):
        obs_surface = results.sel(trajectory=traj, obs=0)
        min_index = np.argmin(results.sel(trajectory=traj)["z"].data)
        obs_maxdepth = results.sel(trajectory=traj, obs=min_index)

        for obs, loc in [
            (obs_surface, "surface"),
            (obs_maxdepth, "maxdepth"),
        ]:
            exp = exp_bothloc[loc]
            for var in [
                "o2",
                "chl",
                "no3",
                "po4",
                "ph",
                "phyc",
                "zooc",
                "nppv",
                "lat",
                "lon",
            ]:
                obs_value = obs[var].values.item()
                exp_value = exp[var]
                assert np.isclose(obs_value, exp_value), (
                    f"Observation incorrect {ctd_i=} {loc=} {var=} {obs_value=} {exp_value=}."
                )
