"""
Test the simulation of CTD instruments.

Fields are kept static over time and time component of CTD measurements is not tested tested because it's tricky to provide expected measurements.
"""

import datetime

import numpy as np
import xarray as xr

from parcels import Field, FieldSet
from virtualship.instruments.ctd import CTD, CTDInstrument
from virtualship.models import Location, Spacetime


def test_simulate_ctds(tmpdir) -> None:
    # arbitrary time offset for the dummy fieldset
    base_time = datetime.datetime.strptime("1950-01-01", "%Y-%m-%d")

    # where to cast CTDs
    ctds = [
        CTD(
            spacetime=Spacetime(
                location=Location(latitude=0, longitude=1),
                time=base_time + datetime.timedelta(hours=0),
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
    u = np.zeros((2, 2, 2, 2))
    v = np.zeros((2, 2, 2, 2))
    t = np.zeros((2, 2, 2, 2))
    s = np.zeros((2, 2, 2, 2))

    t[:, 1, 0, 1] = ctd_exp[0]["surface"]["temperature"]
    t[:, 0, 0, 1] = ctd_exp[0]["maxdepth"]["temperature"]
    t[:, 1, 1, 0] = ctd_exp[1]["surface"]["temperature"]
    t[:, 0, 1, 0] = ctd_exp[1]["maxdepth"]["temperature"]

    s[:, 1, 0, 1] = ctd_exp[0]["surface"]["salinity"]
    s[:, 0, 0, 1] = ctd_exp[0]["maxdepth"]["salinity"]
    s[:, 1, 1, 0] = ctd_exp[1]["surface"]["salinity"]
    s[:, 0, 1, 0] = ctd_exp[1]["maxdepth"]["salinity"]

    fieldset = FieldSet.from_data(
        {"V": v, "U": u, "T": t, "S": s},
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

    # dummy expedition and directory for CTDInstrument
    class DummyExpedition:
        class schedule:
            class space_time_region:
                time_range = type(
                    "TimeRange",
                    (),
                    {
                        "start_time": fieldset.T.grid.time_origin.fulltime(
                            fieldset.T.grid.time_full[0]
                        ),
                        "end_time": fieldset.T.grid.time_origin.fulltime(
                            fieldset.T.grid.time_full[-1]
                        ),
                    },
                )()
                spatial_range = type(
                    "SpatialRange",
                    (),
                    {
                        "minimum_longitude": 0,
                        "maximum_longitude": 1,
                        "minimum_latitude": 0,
                        "maximum_latitude": 1,
                    },
                )()

    expedition = DummyExpedition()

    from_data = None

    ctd_instrument = CTDInstrument(expedition, from_data)
    out_path = tmpdir.join("out.zarr")

    ctd_instrument.load_input_data = lambda: fieldset
    ctd_instrument.simulate(ctds, out_path)

    # test if output is as expected
    results = xr.open_zarr(out_path)

    assert len(results.trajectory) == len(ctds)

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
