"""
Test the simulation of CTD instruments.

Fields are kept static over time and time component of CTD measurements is not tested tested because it's tricky to provide expected measurements.
"""

import datetime

import numpy as np
import parcels
import polars as pl
import pydantic
import pytest
import xarray as xr

from virtualship.instruments.ctd import CTD, CTDInstrument
from virtualship.instruments.sensors import SensorType
from virtualship.instruments.types import InstrumentType
from virtualship.models import Location, Spacetime
from virtualship.models.expedition import (
    CTDConfig,
    InstrumentsConfig,
    SensorConfig,
    Waypoint,
)

BASE_TIME = datetime.datetime.strptime("1950-01-01", "%Y-%m-%d")
MIN_DEPTH = -11
MAX_DEPTH = -2000
STATIONKEEPING_TIME = 50


def create_dummy_expedition(
    sensors, lifetime=datetime.timedelta(days=1), location=(1, 2)
):
    """Create a DummyExpedition class with specified sensors and parameters."""

    class DummyExpedition:
        class schedule:
            waypoints: list[Waypoint] = [  # noqa: RUF012
                Waypoint(location=Location(*location), time=BASE_TIME)
            ]

        instruments_config = InstrumentsConfig(
            ctd_config=CTDConfig(
                stationkeeping_time_minutes=STATIONKEEPING_TIME,
                min_depth_meter=MIN_DEPTH,
                max_depth_meter=MAX_DEPTH,
                sensors=sensors,
            )
        )

    return DummyExpedition()


def create_fieldset(
    data_dict,
    lon_range=(0.0, 1.0),
    lat_range=(0.0, 1.0),
    depth_range=(-1000, 0),
    time_range=None,
    bathymetry_val=-1000.0,
):
    if time_range is None:
        time_range = [
            np.datetime64(BASE_TIME),
            np.datetime64(BASE_TIME + datetime.timedelta(hours=1)),
        ]

    data_vars = {}
    for key, val in data_dict.items():
        data_vars[key] = (("time", "depth", "lat", "lon"), val)

    ds_fields = xr.Dataset(
        data_vars=data_vars,
        coords={
            "lon": (("lon"), np.array(lon_range), {"units": "degrees_east"}),
            "lat": (("lat"), np.array(lat_range), {"units": "degrees_north"}),
            "depth": (("depth"), np.array(depth_range)),
            "time": (
                ("time"),
                time_range,
                {"axis": "T"},
            ),
        },
    )

    fields = {var: ds_fields[var] for var in data_vars.keys()}
    ds_fset = parcels.convert.copernicusmarine_to_sgrid(fields=fields)
    fieldset = parcels.FieldSet.from_sgrid_conventions(ds_fset)

    ds_bathymetry = xr.Dataset(
        data_vars={
            "bathymetry": (
                ("lat", "lon"),
                np.full((len(lat_range), len(lon_range)), bathymetry_val),
            )
        },
        coords={
            "lon": (("lon"), np.array(lon_range), {"units": "degrees_east"}),
            "lat": (("lat"), np.array(lat_range), {"units": "degrees_north"}),
        },
    )
    ds_bathymetry_fset = parcels.convert.copernicusmarine_to_sgrid(
        fields={"bathymetry": ds_bathymetry["bathymetry"]}
    )
    bathymetry_fset = parcels.FieldSet.from_sgrid_conventions(ds_bathymetry_fset)

    fieldset.add_field(bathymetry_fset.bathymetry)

    return fieldset


def test_simulate_ctds(tmpdir) -> None:
    """Test that CTDInstrument simulates measurements correctly, incuding sampling physical and bgc variables."""
    # where to cast CTDs
    ctds = [
        CTD(
            spacetime=Spacetime(
                location=Location(latitude=0, longitude=1),
                time=BASE_TIME + datetime.timedelta(hours=0),
            ),
            min_depth=0,
            max_depth=float("-inf"),
        ),
        CTD(
            spacetime=Spacetime(
                location=Location(latitude=1, longitude=0),
                time=BASE_TIME,
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
                "o2": 10.0,
                "chl": 20.0,
                "no3": 30.0,
                "y": ctds[0].spacetime.location.lat,
                "x": ctds[0].spacetime.location.lon,
            },
            "maxdepth": {
                "salinity": 7,
                "temperature": 8,
                "o2": 11.0,
                "chl": 21.0,
                "no3": 31.0,
                "y": ctds[0].spacetime.location.lat,
                "x": ctds[0].spacetime.location.lon,
            },
        },
        {
            "surface": {
                "salinity": 5,
                "temperature": 6,
                "o2": 12.0,
                "chl": 22.0,
                "no3": 32.0,
                "y": ctds[1].spacetime.location.lat,
                "x": ctds[1].spacetime.location.lon,
            },
            "maxdepth": {
                "salinity": 7,
                "temperature": 8,
                "o2": 13.0,
                "chl": 23.0,
                "no3": 33.0,
                "y": ctds[1].spacetime.location.lat,
                "x": ctds[1].spacetime.location.lon,
            },
        },
    ]

    # create fieldset based on the expected observations
    # indices are time, depth, latitude, longitude
    u = np.zeros((2, 2, 2, 2))
    v = np.zeros((2, 2, 2, 2))
    t = np.zeros((2, 2, 2, 2))
    s = np.zeros((2, 2, 2, 2))
    o2 = np.zeros((2, 2, 2, 2))
    chl = np.zeros((2, 2, 2, 2))
    no3 = np.zeros((2, 2, 2, 2))

    t[:, 1, 0, 1] = ctd_exp[0]["surface"]["temperature"]
    t[:, 0, 0, 1] = ctd_exp[0]["maxdepth"]["temperature"]
    t[:, 1, 1, 0] = ctd_exp[1]["surface"]["temperature"]
    t[:, 0, 1, 0] = ctd_exp[1]["maxdepth"]["temperature"]

    s[:, 1, 0, 1] = ctd_exp[0]["surface"]["salinity"]
    s[:, 0, 0, 1] = ctd_exp[0]["maxdepth"]["salinity"]
    s[:, 1, 1, 0] = ctd_exp[1]["surface"]["salinity"]
    s[:, 0, 1, 0] = ctd_exp[1]["maxdepth"]["salinity"]

    o2[:, 1, 0, 1] = ctd_exp[0]["surface"]["o2"]
    o2[:, 0, 0, 1] = ctd_exp[0]["maxdepth"]["o2"]
    o2[:, 1, 1, 0] = ctd_exp[1]["surface"]["o2"]
    o2[:, 0, 1, 0] = ctd_exp[1]["maxdepth"]["o2"]

    chl[:, 1, 0, 1] = ctd_exp[0]["surface"]["chl"]
    chl[:, 0, 0, 1] = ctd_exp[0]["maxdepth"]["chl"]
    chl[:, 1, 1, 0] = ctd_exp[1]["surface"]["chl"]
    chl[:, 0, 1, 0] = ctd_exp[1]["maxdepth"]["chl"]

    no3[:, 1, 0, 1] = ctd_exp[0]["surface"]["no3"]
    no3[:, 0, 0, 1] = ctd_exp[0]["maxdepth"]["no3"]
    no3[:, 1, 1, 0] = ctd_exp[1]["surface"]["no3"]
    no3[:, 0, 1, 0] = ctd_exp[1]["maxdepth"]["no3"]

    fieldset = create_fieldset(
        {"V": v, "U": u, "T": t, "S": s, "o2": o2, "chl": chl, "no3": no3},
        time_range=[
            np.datetime64(BASE_TIME + datetime.timedelta(hours=0)),
            np.datetime64(BASE_TIME + datetime.timedelta(hours=1)),
        ],
    )

    sensors = [
        SensorConfig(sensor_type=SensorType.TEMPERATURE),
        SensorConfig(sensor_type=SensorType.SALINITY),
        SensorConfig(sensor_type=SensorType.OXYGEN),
        SensorConfig(sensor_type=SensorType.CHLOROPHYLL),
        SensorConfig(sensor_type=SensorType.NITRATE),
    ]

    expedition = create_dummy_expedition(sensors)
    from_data = None

    ctd_instrument = CTDInstrument(expedition, from_data)
    out_path = tmpdir.join("out.parquet")

    ctd_instrument.load_input_data = lambda: fieldset
    ctd_instrument.simulate(ctds, out_path)

    # test if output is as expected
    results = parcels.read_particlefile(out_path)

    assert np.unique(results["particle_id"].to_numpy()).size == len(ctds)

    for ctd_i, id in enumerate(np.unique(results["particle_id"].to_numpy())):
        ctd_df = results.filter(pl.col("particle_id") == id)
        ctd_surface = ctd_df.filter(pl.col("z") == ctd_df["z"].max())[
            0
        ]  # one row (there are two given ctd ascends back to surface)
        ctd_maxdepth = ctd_df.filter(pl.col("z") == ctd_df["z"].min())

        for obs, loc in [
            (ctd_surface, "surface"),
            (ctd_maxdepth, "maxdepth"),
        ]:
            exp = ctd_exp[ctd_i][loc]

            for var in ["salinity", "temperature", "o2", "chl", "no3", "y", "x"]:
                obs_value = obs[var].item()
                exp_value = exp[var]

                assert np.isclose(obs_value, exp_value), (
                    f"Observation incorrect {ctd_i=} {loc=} {var=} {obs_value=} {exp_value=}."
                )


def test_ctd_sensor_config_active_variables() -> None:
    """active_variables() only returns variables for enabled sensors."""
    config_both = CTDConfig(
        stationkeeping_time_minutes=50,
        min_depth_meter=-11.0,
        max_depth_meter=-2000.0,
        sensors=[
            SensorConfig(sensor_type=SensorType.TEMPERATURE),
            SensorConfig(sensor_type=SensorType.OXYGEN),
        ],
    )
    assert config_both.active_variables() == {"T": "thetao", "o2": "o2"}

    config_temp_only = CTDConfig(
        stationkeeping_time_minutes=50,
        min_depth_meter=-11.0,
        max_depth_meter=-2000.0,
        sensors=[
            SensorConfig(sensor_type=SensorType.TEMPERATURE)
        ],  # SALINITY absent = disabled
    )
    assert config_temp_only.active_variables() == {"T": "thetao"}


def test_ctd_sensor_config_yaml() -> None:
    """CTDConfig sensors survive YAML serialisation."""
    config = CTDConfig(
        stationkeeping_time_minutes=50,
        min_depth_meter=-11.0,
        max_depth_meter=-2000.0,
        sensors=[
            SensorConfig(sensor_type=SensorType.TEMPERATURE),
            SensorConfig(sensor_type=SensorType.OXYGEN),
        ],  # SALINITY omitted = disabled
    )
    dumped = config.model_dump(by_alias=True)
    loaded = CTDConfig.model_validate(dumped)

    assert len(loaded.sensors) == 2
    assert loaded.sensors[0].sensor_type == SensorType.TEMPERATURE
    assert loaded.sensors[0].enabled is True
    assert loaded.sensors[1].sensor_type == SensorType.OXYGEN
    assert loaded.sensors[1].enabled is True


def test_ctd_disabled_sensor_absent(tmpdir) -> None:
    """Variables for disabled sensors must not appear in the output."""
    base_time = datetime.datetime.strptime("1950-01-01", "%Y-%m-%d")

    ctds = [
        CTD(
            spacetime=Spacetime(
                location=Location(latitude=0, longitude=0),
                time=base_time,
            ),
            min_depth=0,
            max_depth=-20,
        ),
    ]

    # Only temperature field, no salinty
    t = np.full((2, 2, 2, 2), 5.0)
    fieldset = create_fieldset(
        {"T": t},
        time_range=[
            np.datetime64(base_time + datetime.timedelta(seconds=0)),
            np.datetime64(base_time + datetime.timedelta(hours=4)),
        ],
        lat_range=np.array([0.0, 1.0]),
        lon_range=np.array([0.0, 1.0]),
    )

    sensors = [
        SensorConfig(sensor_type=SensorType.TEMPERATURE)
    ]  # SALINITY omitted = disabled

    expedition = create_dummy_expedition(sensors)
    ctd_instrument = CTDInstrument(expedition, None)
    out_path = tmpdir.join("out_disabled.parquet")
    ctd_instrument.load_input_data = lambda: fieldset
    ctd_instrument.simulate(ctds, out_path)

    results = parcels.read_particlefile(out_path)
    assert "temperature" in results, "Enabled sensor variable must be present"
    assert "salinity" not in results, (
        "Disabled sensor variable must be absent from output"
    )


def test_ctd_supported_sensors():
    """CTD supports TEMPERATURE, SALINITY and all BGC sensors."""
    from virtualship.utils import get_supported_sensors

    assert get_supported_sensors(InstrumentType.CTD) == frozenset(
        {
            SensorType.TEMPERATURE,
            SensorType.SALINITY,
            SensorType.OXYGEN,
            SensorType.CHLOROPHYLL,
            SensorType.NITRATE,
            SensorType.PHOSPHATE,
            SensorType.PH,
            SensorType.PHYTOPLANKTON,
            SensorType.PRIMARY_PRODUCTION,
        }
    )


def test_ctd_config_default_sensors():
    """CTDConfig defaults to all supported sensors (phys + bgc)."""
    config = CTDConfig(
        stationkeeping_time_minutes=50,
        min_depth_meter=-11.0,
        max_depth_meter=-2000.0,
    )
    types = {sc.sensor_type for sc in config.sensors}
    assert types == {
        SensorType.TEMPERATURE,
        SensorType.SALINITY,
        SensorType.OXYGEN,
        SensorType.CHLOROPHYLL,
        SensorType.NITRATE,
        SensorType.PHOSPHATE,
        SensorType.PH,
        SensorType.PHYTOPLANKTON,
        SensorType.PRIMARY_PRODUCTION,
    }


# TODO: may need to be removed if add ADCP to CTDs in future PR...
def test_ctd_config_unsupported_sensor_rejected():
    """Unsupported sensor on CTD is rejected."""
    with pytest.raises(pydantic.ValidationError, match="does not support"):
        CTDConfig(
            stationkeeping_time_minutes=50,
            min_depth_meter=-11.0,
            max_depth_meter=-2000.0,
            sensors=[SensorConfig(sensor_type=SensorType.VELOCITY)],
        )


def test_sensor_absent(tmpdir) -> None:
    """A (BGC) sensor that is disabled must not appear in the output."""
    base_time = datetime.datetime.strptime("1950-01-01", "%Y-%m-%d")

    ctds = [
        CTD(
            spacetime=Spacetime(
                location=Location(latitude=0, longitude=0),
                time=base_time,
            ),
            min_depth=0,
            max_depth=-20,
        ),
    ]

    o2_data = np.full((2, 2, 2, 2), 5.0)
    fieldset = create_fieldset(
        {"o2": o2_data},
        time_range=[
            np.datetime64(base_time + datetime.timedelta(seconds=0)),
            np.datetime64(base_time + datetime.timedelta(hours=4)),
        ],
        lat_range=np.array([0.0, 1.0]),
        lon_range=np.array([0.0, 1.0]),
    )

    sensors = [
        SensorConfig(sensor_type=SensorType.OXYGEN)
        # CHLOROPHYLL omitted = disabled
    ]

    expedition = create_dummy_expedition(sensors)
    ctd_instrument = CTDInstrument(expedition, None)
    out_path = tmpdir.join("out_bgc_disabled.parquet")
    ctd_instrument.load_input_data = lambda: fieldset
    ctd_instrument.simulate(ctds, out_path)

    results = parcels.read_particlefile(out_path)
    assert "o2" in results, "Enabled BGC sensor variable must be present"
    assert "chl" not in results, "Disabled sensor variable must be absent from output"


def test_ctd_instrument_type():
    """CTDInstrument returns the correct InstrumentType and if is underway instrument."""
    sensors = [SensorConfig(sensor_type=SensorType.TEMPERATURE)]  # only need one
    expedition = create_dummy_expedition(sensors)

    ctd_instrument = CTDInstrument(expedition, from_data=None)
    assert ctd_instrument.instrument_type == InstrumentType.CTD
    assert not ctd_instrument.instrument_type.is_underway
