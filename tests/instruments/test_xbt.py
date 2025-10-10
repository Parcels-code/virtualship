"""
Test the simulation of XBT instruments.

Fields are kept static over time and time component of XBT measurements is not tested tested because it's tricky to provide expected measurements.
"""

import datetime
from datetime import timedelta

import numpy as np
import xarray as xr
from parcels import Field, FieldSet

from virtualship.instruments.xbt import XBT, simulate_xbt
from virtualship.models import Location, Spacetime


def test_simulate_xbts(tmpdir) -> None:
    # arbitrary time offset for the dummy fieldset
    base_time = datetime.datetime.strptime("1950-01-01", "%Y-%m-%d")

    # where to cast XBTs
    xbts = [
        XBT(
            spacetime=Spacetime(
                location=Location(latitude=0, longitude=1),
                time=base_time + datetime.timedelta(hours=0),
            ),
            min_depth=0,
            max_depth=float("-inf"),
            fall_speed=6.553,
            deceleration_coefficient=0.00242,
        ),
        XBT(
            spacetime=Spacetime(
                location=Location(latitude=1, longitude=0),
                time=base_time,
            ),
            min_depth=0,
            max_depth=float("-inf"),
            fall_speed=6.553,
            deceleration_coefficient=0.00242,
        ),
    ]

    # expected observations for xbts at surface and at maximum depth
    xbt_exp = [
        {
            "surface": {
                "temperature": 6,
                "lat": xbts[0].spacetime.location.lat,
                "lon": xbts[0].spacetime.location.lon,
            },
            "maxdepth": {
                "temperature": 8,
                "lat": xbts[0].spacetime.location.lat,
                "lon": xbts[0].spacetime.location.lon,
            },
        },
        {
            "surface": {
                "temperature": 6,
                "lat": xbts[1].spacetime.location.lat,
                "lon": xbts[1].spacetime.location.lon,
            },
            "maxdepth": {
                "temperature": 8,
                "lat": xbts[1].spacetime.location.lat,
                "lon": xbts[1].spacetime.location.lon,
            },
        },
    ]

    # create fieldset based on the expected observations
    # indices are time, depth, latitude, longitude
    u = np.zeros((2, 2, 2, 2))
    v = np.zeros((2, 2, 2, 2))
    t = np.zeros((2, 2, 2, 2))

    t[:, 1, 0, 1] = xbt_exp[0]["surface"]["temperature"]
    t[:, 0, 0, 1] = xbt_exp[0]["maxdepth"]["temperature"]
    t[:, 1, 1, 0] = xbt_exp[1]["surface"]["temperature"]
    t[:, 0, 1, 0] = xbt_exp[1]["maxdepth"]["temperature"]

    fieldset = FieldSet.from_data(
        {"V": v, "U": u, "T": t},
        {
            "time": [
                np.datetime64(base_time + datetime.timedelta(hours=0)),
                np.datetime64(base_time + datetime.timedelta(hours=1)),
            ],
            "depth": [-1000, 0],
            "lat": [0, 1],
            "lon": [0, 1],
        },
    )
    fieldset.add_field(Field("bathymetry", [-1000], lon=0, lat=0))

    # perform simulation
    out_path = tmpdir.join("out.zarr")

    simulate_xbt(
        xbts=xbts,
        fieldset=fieldset,
        out_path=out_path,
        outputdt=timedelta(seconds=10),
    )

    # test if output is as expected
    results = xr.open_zarr(out_path)

    assert len(results.trajectory) == len(xbts)

    for xbt_i, (traj, exp_bothloc) in enumerate(
        zip(results.trajectory, xbt_exp, strict=True)
    ):
        obs_surface = results.sel(trajectory=traj, obs=0)
        min_index = np.argmin(results.sel(trajectory=traj)["z"].data)
        obs_maxdepth = results.sel(trajectory=traj, obs=min_index)

        for obs, loc in [
            (obs_surface, "surface"),
            (obs_maxdepth, "maxdepth"),
        ]:
            exp = exp_bothloc[loc]
            for var in ["temperature", "lat", "lon"]:
                obs_value = obs[var].values.item()
                exp_value = exp[var]
                assert np.isclose(obs_value, exp_value), (
                    f"Observation incorrect {xbt_i=} {loc=} {var=} {obs_value=} {exp_value=}."
                )
