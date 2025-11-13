"""Test the simulation of ship salinity temperature measurements."""

import datetime

import numpy as np
import xarray as xr
from parcels import FieldSet

from virtualship.instruments.ship_underwater_st import simulate_ship_underwater_st
from virtualship.models import Location, Spacetime


def test_simulate_ship_underwater_st(tmpdir) -> None:
    # depth at which the sampling will be done
    DEPTH = -2

    # arbitrary time offset for the dummy fieldset
    base_time = datetime.datetime.strptime("1950-01-01", "%Y-%m-%d")

    # where to sample
    sample_points = [
        Spacetime(Location(1, 2), base_time + datetime.timedelta(seconds=0)),
        Spacetime(Location(3, 4), base_time + datetime.timedelta(seconds=1)),
    ]

    # expected observations at sample points
    expected_obs = [
        {
            "S": 5,
            "T": 6,
            "lat": sample_points[0].location.lat,
            "lon": sample_points[0].location.lon,
            "time": base_time + datetime.timedelta(seconds=0),
        },
        {
            "S": 7,
            "T": 8,
            "lat": sample_points[1].location.lat,
            "lon": sample_points[1].location.lon,
            "time": base_time + datetime.timedelta(seconds=1),
        },
    ]

    # create fieldset based on the expected observations
    # indices are time, latitude, longitude
    salinity = np.zeros((2, 2, 2))
    salinity[0, 0, 0] = expected_obs[0]["S"]
    salinity[1, 1, 1] = expected_obs[1]["S"]

    temperature = np.zeros((2, 2, 2))
    temperature[0, 0, 0] = expected_obs[0]["T"]
    temperature[1, 1, 1] = expected_obs[1]["T"]

    fieldset = FieldSet.from_data(
        {
            "V": np.zeros((2, 2, 2)),
            "U": np.zeros((2, 2, 2)),
            "S": salinity,
            "T": temperature,
        },
        {
            "lat": np.array([expected_obs[0]["lat"], expected_obs[1]["lat"]]),
            "lon": np.array([expected_obs[0]["lon"], expected_obs[1]["lon"]]),
            "time": np.array(
                [
                    np.datetime64(expected_obs[0]["time"]),
                    np.datetime64(expected_obs[1]["time"]),
                ]
            ),
        },
    )

    # perform simulation
    out_path = tmpdir.join("out.zarr")

    simulate_ship_underwater_st(
        fieldset=fieldset,
        out_path=out_path,
        depth=DEPTH,
        sample_points=sample_points,
    )

    # test if output is as expected
    results = xr.open_zarr(out_path)

    assert len(results.trajectory) == 1  # expect a single trajectory
    traj = results.trajectory.item()
    assert len(results.sel(trajectory=traj).obs) == len(
        sample_points
    )  # expect as many obs as sample points

    # for every obs, check if the variables match the expected observations
    for i, (obs_i, exp) in enumerate(
        zip(results.sel(trajectory=traj).obs, expected_obs, strict=True)
    ):
        obs = results.sel(trajectory=traj, obs=obs_i)
        for var in ["S", "T", "lat", "lon"]:
            obs_value = obs[var].values.item()
            exp_value = exp[var]
            assert np.isclose(obs_value, exp_value), (
                f"Observation incorrect {i=} {var=} {obs_value=} {exp_value=}."
            )
