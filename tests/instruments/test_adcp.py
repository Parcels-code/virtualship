"""Test the simulation of ADCP instruments."""

import datetime

import numpy as np
import xarray as xr

from parcels import FieldSet
from virtualship.instruments.adcp import ADCPInstrument
from virtualship.models import Location, Spacetime


def test_simulate_adcp(tmpdir) -> None:
    # maximum depth the ADCP can measure
    MAX_DEPTH = -1000  # -1000
    # minimum depth the ADCP can measure
    MIN_DEPTH = -5  # -5
    # How many samples to take in the complete range between max_depth and min_depth.
    NUM_BINS = 40

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
            "V": {"surface": 5, "max_depth": 6},
            "U": {"surface": 7, "max_depth": 8},
            "lat": sample_points[0].location.lat,
            "lon": sample_points[0].location.lon,
            "time": base_time + datetime.timedelta(seconds=0),
        },
        {
            "V": {"surface": 9, "max_depth": 10},
            "U": {"surface": 11, "max_depth": 12},
            "lat": sample_points[1].location.lat,
            "lon": sample_points[1].location.lon,
            "time": base_time + datetime.timedelta(seconds=1),
        },
    ]

    # create fieldset based on the expected observations
    # indices are time, depth, latitude, longitude
    v = np.zeros((2, 2, 2, 2))
    v[0, 0, 0, 0] = expected_obs[0]["V"]["max_depth"]
    v[0, 1, 0, 0] = expected_obs[0]["V"]["surface"]
    v[1, 0, 1, 1] = expected_obs[1]["V"]["max_depth"]
    v[1, 1, 1, 1] = expected_obs[1]["V"]["surface"]

    u = np.zeros((2, 2, 2, 2))
    u[0, 0, 0, 0] = expected_obs[0]["U"]["max_depth"]
    u[0, 1, 0, 0] = expected_obs[0]["U"]["surface"]
    u[1, 0, 1, 1] = expected_obs[1]["U"]["max_depth"]
    u[1, 1, 1, 1] = expected_obs[1]["U"]["surface"]

    fieldset = FieldSet.from_data(
        {
            "V": v,
            "U": u,
        },
        {
            "lat": np.array([expected_obs[0]["lat"], expected_obs[1]["lat"]]),
            "lon": np.array([expected_obs[0]["lon"], expected_obs[1]["lon"]]),
            "depth": np.array([MAX_DEPTH, MIN_DEPTH]),
            "time": np.array(
                [
                    np.datetime64(expected_obs[0]["time"]),
                    np.datetime64(expected_obs[1]["time"]),
                ]
            ),
        },
    )

    # dummy expedition and directory for ADCPInstrument
    class DummyExpedition:
        class instruments_config:
            class adcp_config:
                max_depth_meter = MAX_DEPTH
                num_bins = NUM_BINS

    expedition = DummyExpedition()
    directory = tmpdir
    from_data = None

    adcp_instrument = ADCPInstrument(expedition, directory, from_data)
    out_path = tmpdir.join("out.zarr")

    adcp_instrument.load_input_data = lambda: fieldset
    adcp_instrument.simulate(sample_points, out_path)

    results = xr.open_zarr(out_path)

    # test if output is as expected
    assert len(results.trajectory) == NUM_BINS

    # for every obs, check if the variables match the expected observations
    # we only verify at the surface and max depth of the adcp, because in between is tricky
    for traj, vert_loc in [
        (results.trajectory[0], "max_depth"),
        (results.trajectory[-1], "surface"),
    ]:
        obs_all = results.sel(trajectory=traj).obs
        assert len(obs_all) == len(sample_points)
        for i, (obs_i, exp) in enumerate(zip(obs_all, expected_obs, strict=True)):
            obs = results.sel(trajectory=traj, obs=obs_i)
            for var in ["lat", "lon"]:
                obs_value = obs[var].values.item()
                exp_value = exp[var]
                assert np.isclose(obs_value, exp_value), (
                    f"Observation incorrect {vert_loc=} {obs_i=} {var=} {obs_value=} {exp_value=}."
                )
            for var in ["V", "U"]:
                obs_value = obs[var].values.item()
                exp_value = exp[var][vert_loc]
                assert np.isclose(obs_value, exp_value), (
                    f"Observation incorrect {vert_loc=} {i=} {var=} {obs_value=} {exp_value=}."
                )
