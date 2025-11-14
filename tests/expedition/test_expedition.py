from datetime import datetime, timedelta
from pathlib import Path
from unittest.mock import patch

import numpy as np
import pyproj
import pytest
import xarray as xr
from parcels import FieldSet

from virtualship.errors import InstrumentsConfigError, ScheduleError
from virtualship.models import (
    Expedition,
    Location,
    Schedule,
    Waypoint,
)
from virtualship.models.space_time_region import (
    SpaceTimeRegion,
    SpatialRange,
    TimeRange,
)
from virtualship.utils import EXPEDITION, _get_expedition, get_example_expedition

projection = pyproj.Geod(ellps="WGS84")

expedition_dir = Path("expedition_dir")


def test_import_export_expedition(tmpdir) -> None:
    out_path = tmpdir.join(EXPEDITION)

    # arbitrary time for testing
    base_time = datetime.strptime("1950-01-01", "%Y-%m-%d")

    schedule = Schedule(
        waypoints=[
            Waypoint(location=Location(0, 0), time=base_time, instrument=None),
            Waypoint(
                location=Location(1, 1),
                time=base_time + timedelta(hours=1),
                instrument=None,
            ),
        ]
    )
    get_expedition = _get_expedition(expedition_dir)
    expedition = Expedition(
        schedule=schedule,
        instruments_config=get_expedition.instruments_config,
        ship_config=get_expedition.ship_config,
    )
    expedition.to_yaml(out_path)

    expedition2 = Expedition.from_yaml(out_path)
    assert expedition == expedition2


def test_verify_schedule() -> None:
    schedule = Schedule(
        waypoints=[
            Waypoint(location=Location(0, 0), time=datetime(2022, 1, 1, 1, 0, 0)),
            Waypoint(location=Location(1, 0), time=datetime(2022, 1, 2, 1, 0, 0)),
        ]
    )

    ship_speed_knots = _get_expedition(expedition_dir).ship_config.ship_speed_knots

    schedule.verify(ship_speed_knots, ignore_land_test=True)


def test_get_instruments() -> None:
    get_expedition = _get_expedition(expedition_dir)
    schedule = Schedule(
        waypoints=[
            Waypoint(location=Location(0, 0), instrument=["CTD"]),
            Waypoint(location=Location(1, 0), instrument=["XBT", "ARGO_FLOAT"]),
            Waypoint(location=Location(1, 0), instrument=["CTD"]),
        ]
    )
    expedition = Expedition(
        schedule=schedule,
        instruments_config=get_expedition.instruments_config,
        ship_config=get_expedition.ship_config,
    )
    assert (
        set(instrument.name for instrument in expedition.get_instruments())
        == {
            "CTD",
            "UNDERWATER_ST",  # not added above but underway instruments are auto present from instruments_config in expedition_dir/expedition.yaml
            "ADCP",  # as above
            "ARGO_FLOAT",
            "XBT",
        }
    )


def test_verify_on_land():
    """Test that schedule verification raises error for waypoints on land (0.0 m bathymetry)."""
    # bathymetry fieldset with NaNs at specific locations
    latitude = np.array([0, 1.0, 2.0])
    longitude = np.array([0, 1.0, 2.0])
    bathymetry = np.array(
        [
            [100, 0.0, 100],
            [100, 100, 0.0],
            [0.0, 100, 100],
        ]
    )

    ds_bathymetry = xr.Dataset(
        {
            "deptho": (("latitude", "longitude"), bathymetry),
        },
        coords={
            "latitude": latitude,
            "longitude": longitude,
        },
    )

    bathymetry_variables = {"bathymetry": "deptho"}
    bathymetry_dimensions = {"lon": "longitude", "lat": "latitude"}
    bathymetry_fieldset = FieldSet.from_xarray_dataset(
        ds_bathymetry, bathymetry_variables, bathymetry_dimensions
    )

    # waypoints placed in NaN bathy cells
    waypoints = [
        Waypoint(
            location=Location(0.0, 1.0), time=datetime(2022, 1, 1, 1, 0, 0)
        ),  # NaN cell
        Waypoint(
            location=Location(1.0, 2.0), time=datetime(2022, 1, 2, 1, 0, 0)
        ),  # NaN cell
        Waypoint(
            location=Location(2.0, 0.0), time=datetime(2022, 1, 3, 1, 0, 0)
        ),  # NaN cell
    ]

    spatial_range = SpatialRange(
        minimum_latitude=min(wp.location.lat for wp in waypoints),
        maximum_latitude=max(wp.location.lat for wp in waypoints),
        minimum_longitude=min(wp.location.lon for wp in waypoints),
        maximum_longitude=max(wp.location.lon for wp in waypoints),
    )
    time_range = TimeRange(
        start_time=min(wp.time for wp in waypoints if wp.time is not None),
        end_time=max(wp.time for wp in waypoints if wp.time is not None),
    )
    space_time_region = SpaceTimeRegion(
        spatial_range=spatial_range, time_range=time_range
    )
    schedule = Schedule(waypoints=waypoints, space_time_region=space_time_region)
    ship_speed_knots = _get_expedition(expedition_dir).ship_config.ship_speed_knots

    with patch(
        "virtualship.models.expedition._get_bathy_data",
        return_value=bathymetry_fieldset,
    ):
        with pytest.raises(
            ScheduleError,
            match=r"The following waypoint\(s\) throw\(s\) error\(s\):",
        ):
            schedule.verify(
                ship_speed_knots,
                ignore_land_test=False,
                from_data=None,
            )


@pytest.mark.parametrize(
    "schedule,check_space_time_region,error,match",
    [
        pytest.param(
            Schedule(waypoints=[]),
            False,
            ScheduleError,
            "At least one waypoint must be provided.",
            id="NoWaypoints",
        ),
        pytest.param(
            Schedule(
                waypoints=[
                    Waypoint(location=Location(0, 0)),
                    Waypoint(
                        location=Location(1, 0), time=datetime(2022, 1, 1, 1, 0, 0)
                    ),
                ]
            ),
            False,
            ScheduleError,
            "First waypoint must have a specified time.",
            id="FirstWaypointHasTime",
        ),
        pytest.param(
            Schedule(
                waypoints=[
                    Waypoint(
                        location=Location(0, 0), time=datetime(2022, 1, 2, 1, 0, 0)
                    ),
                    Waypoint(location=Location(0, 0)),
                    Waypoint(
                        location=Location(1, 0), time=datetime(2022, 1, 1, 1, 0, 0)
                    ),
                ]
            ),
            False,
            ScheduleError,
            "Waypoint\\(s\\) : each waypoint should be timed after all previous waypoints",
            id="SequentialWaypoints",
        ),
        pytest.param(
            Schedule(
                waypoints=[
                    Waypoint(
                        location=Location(0, 0), time=datetime(2022, 1, 1, 1, 0, 0)
                    ),
                    Waypoint(
                        location=Location(1, 0), time=datetime(2022, 1, 1, 1, 1, 0)
                    ),
                ]
            ),
            False,
            ScheduleError,
            "Waypoint planning is not valid: would arrive too late at waypoint number 2...",
            id="NotEnoughTime",
        ),
        pytest.param(
            Schedule(
                waypoints=[
                    Waypoint(
                        location=Location(0, 0), time=datetime(2022, 1, 1, 1, 0, 0)
                    ),
                    Waypoint(
                        location=Location(1, 0), time=datetime(2022, 1, 2, 1, 1, 0)
                    ),
                ]
            ),
            True,
            ScheduleError,
            "space_time_region not found in schedule, please define it to proceed.",
            id="NoSpaceTimeRegion",
        ),
    ],
)
def test_verify_schedule_errors(
    schedule: Schedule, check_space_time_region: bool, error, match
) -> None:
    expedition = _get_expedition(expedition_dir)

    with pytest.raises(error, match=match):
        schedule.verify(
            expedition.ship_config.ship_speed_knots,
            ignore_land_test=True,
            check_space_time_region=check_space_time_region,
        )


@pytest.fixture
def expedition(tmp_file):
    with open(tmp_file, "w") as file:
        file.write(get_example_expedition())
    return Expedition.from_yaml(tmp_file)


@pytest.fixture
def expedition_no_xbt(expedition):
    for waypoint in expedition.schedule.waypoints:
        if waypoint.instrument and any(
            instrument.name == "XBT" for instrument in waypoint.instrument
        ):
            waypoint.instrument = [
                instrument
                for instrument in waypoint.instrument
                if instrument.name != "XBT"
            ]

    return expedition


@pytest.fixture
def instruments_config_no_xbt(expedition):
    delattr(expedition.instruments_config, "xbt_config")
    return expedition.instruments_config


@pytest.fixture
def instruments_config_no_ctd(expedition):
    delattr(expedition.instruments_config, "ctd_config")
    return expedition.instruments_config


@pytest.fixture
def instruments_config_no_ctd_bgc(expedition):
    delattr(expedition.instruments_config, "ctd_bgc_config")
    return expedition.instruments_config


@pytest.fixture
def instruments_config_no_argo_float(expedition):
    delattr(expedition.instruments_config, "argo_float_config")
    return expedition.instruments_config


@pytest.fixture
def instruments_config_no_drifter(expedition):
    delattr(expedition.instruments_config, "drifter_config")
    return expedition.instruments_config


@pytest.fixture
def instruments_config_no_adcp(expedition):
    delattr(expedition.instruments_config, "adcp_config")
    return expedition.instruments_config


@pytest.fixture
def instruments_config_no_underwater_st(expedition):
    delattr(expedition.instruments_config, "ship_underwater_st_config")
    return expedition.instruments_config


def test_verify_instruments_config(expedition) -> None:
    expedition.instruments_config.verify(expedition)


def test_verify_instruments_config_no_instrument(expedition, expedition_no_xbt) -> None:
    expedition.instruments_config.verify(expedition_no_xbt)


@pytest.mark.parametrize(
    "instruments_config_fixture,error,match",
    [
        pytest.param(
            "instruments_config_no_xbt",
            InstrumentsConfigError,
            "Expedition includes instrument 'XBT', but instruments_config does not provide configuration for it.",
            id="InstrumentsConfigNoXBT",
        ),
        pytest.param(
            "instruments_config_no_ctd",
            InstrumentsConfigError,
            "Expedition includes instrument 'CTD', but instruments_config does not provide configuration for it.",
            id="InstrumentsConfigNoCTD",
        ),
        pytest.param(
            "instruments_config_no_ctd_bgc",
            InstrumentsConfigError,
            "Expedition includes instrument 'CTD_BGC', but instruments_config does not provide configuration for it.",
            id="InstrumentsConfigNoCTD_BGC",
        ),
        pytest.param(
            "instruments_config_no_argo_float",
            InstrumentsConfigError,
            "Expedition includes instrument 'ARGO_FLOAT', but instruments_config does not provide configuration for it.",
            id="InstrumentsConfigNoARGO_FLOAT",
        ),
        pytest.param(
            "instruments_config_no_drifter",
            InstrumentsConfigError,
            "Expedition includes instrument 'DRIFTER', but instruments_config does not provide configuration for it.",
            id="InstrumentsConfigNoDRIFTER",
        ),
        pytest.param(
            "instruments_config_no_adcp",
            InstrumentsConfigError,
            r"Underway instrument config attribute\(s\) are missing from YAML\. Must be <Instrument>Config object or None\.",
            id="InstrumentsConfigNoADCP",
        ),
        pytest.param(
            "instruments_config_no_underwater_st",
            InstrumentsConfigError,
            r"Underway instrument config attribute\(s\) are missing from YAML\. Must be <Instrument>Config object or None\.",
            id="InstrumentsConfigNoUNDERWATER_ST",
        ),
    ],
)
def test_verify_instruments_config_errors(
    request, expedition, instruments_config_fixture, error, match
) -> None:
    instruments_config = request.getfixturevalue(instruments_config_fixture)

    with pytest.raises(error, match=match):
        instruments_config.verify(expedition)
