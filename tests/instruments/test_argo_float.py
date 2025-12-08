"""Test the simulation of Argo floats."""

from datetime import datetime, timedelta

import numpy as np
import xarray as xr

from parcels import FieldSet
from virtualship.instruments.argo_float import ArgoFloat, ArgoFloatInstrument
from virtualship.models import Location, Spacetime


def test_simulate_argo_floats(tmpdir) -> None:
    # arbitrary time offset for the dummy fieldset
    base_time = datetime.strptime("1950-01-01", "%Y-%m-%d")

    DRIFT_DEPTH = -1000
    MAX_DEPTH = -2000
    VERTICAL_SPEED = -0.10
    CYCLE_DAYS = 10
    DRIFT_DAYS = 9

    CONST_TEMPERATURE = 1.0  # constant temperature in fieldset
    CONST_SALINITY = 1.0  # constant salinity in fieldset

    v = np.full((2, 2, 2), 1.0)
    u = np.full((2, 2, 2), 1.0)
    t = np.full((2, 2, 2), CONST_TEMPERATURE)
    s = np.full((2, 2, 2), CONST_SALINITY)
    bathy = np.full((2, 2), -5000.0)

    fieldset = FieldSet.from_data(
        {"V": v, "U": u, "T": t, "S": s},
        {
            "lon": np.array([0.0, 10.0]),
            "lat": np.array([0.0, 10.0]),
            "time": [
                np.datetime64(base_time + timedelta(seconds=0)),
                np.datetime64(base_time + timedelta(hours=4)),
            ],
        },
    )
    fieldset.add_field(
        FieldSet.from_data(
            {"bathymetry": bathy},
            {
                "lon": np.array([0.0, 10.0]),
                "lat": np.array([0.0, 10.0]),
            },
        ).bathymetry
    )

    # argo floats to deploy
    argo_floats = [
        ArgoFloat(
            spacetime=Spacetime(location=Location(latitude=0, longitude=0), time=0),
            min_depth=0.0,
            max_depth=MAX_DEPTH,
            drift_depth=DRIFT_DEPTH,
            vertical_speed=VERTICAL_SPEED,
            cycle_days=CYCLE_DAYS,
            drift_days=DRIFT_DAYS,
        )
    ]

    # dummy expedition and directory for ArgoFloatInstrument
    class DummyExpedition:
        pass

    expedition = DummyExpedition()
    from_data = None

    argo_instrument = ArgoFloatInstrument(expedition, from_data)
    out_path = tmpdir.join("out.zarr")

    argo_instrument.load_input_data = lambda: fieldset
    argo_instrument.simulate(argo_floats, out_path)

    # test if output is as expected
    results = xr.open_zarr(out_path)

    # check the following variables are in the dataset
    assert len(results.trajectory) == len(argo_floats)
    for var in ["lon", "lat", "z", "temperature", "salinity"]:
        assert var in results, f"Results don't contain {var}"
