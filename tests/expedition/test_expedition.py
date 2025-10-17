from datetime import datetime, timedelta
from pathlib import Path

import pyproj
import pytest

from virtualship.errors import ConfigError, ScheduleError
from virtualship.expedition.do_expedition import _load_input_data
from virtualship.models import Expedition, Location, Schedule, Waypoint
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
    ship_config = _get_expedition(expedition_dir).ship_config
    expedition = Expedition(schedule=schedule, ship_config=ship_config)
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

    ship_config = _get_expedition(expedition_dir).ship_config

    schedule.verify(ship_config.ship_speed_knots, None)


def test_get_instruments() -> None:
    schedule = Schedule(
        waypoints=[
            Waypoint(location=Location(0, 0), instrument=["CTD"]),
            Waypoint(location=Location(1, 0), instrument=["XBT", "ARGO_FLOAT"]),
            Waypoint(location=Location(1, 0), instrument=["CTD"]),
        ]
    )

    assert set(instrument.name for instrument in schedule.get_instruments()) == {
        "CTD",
        "XBT",
        "ARGO_FLOAT",
    }


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
            "space_time_region not found in schedule, please define it to fetch the data.",
            id="NoSpaceTimeRegion",
        ),
    ],
)
def test_verify_schedule_errors(
    schedule: Schedule, check_space_time_region: bool, error, match
) -> None:
    ship_config = _get_expedition(expedition_dir).ship_config

    input_data = _load_input_data(
        expedition_dir,
        schedule,
        ship_config,
        input_data=Path("expedition_dir/input_data"),
    )

    with pytest.raises(error, match=match):
        schedule.verify(
            ship_config.ship_speed_knots,
            input_data,
            check_space_time_region=check_space_time_region,
        )


@pytest.fixture
def schedule(tmp_file):
    with open(tmp_file, "w") as file:
        file.write(get_example_expedition())
    return Expedition.from_yaml(tmp_file).schedule


@pytest.fixture
def schedule_no_xbt(schedule):
    for waypoint in schedule.waypoints:
        if waypoint.instrument and any(
            instrument.name == "XBT" for instrument in waypoint.instrument
        ):
            waypoint.instrument = [
                instrument
                for instrument in waypoint.instrument
                if instrument.name != "XBT"
            ]

    return schedule


@pytest.fixture
def ship_config(tmp_file):
    with open(tmp_file, "w") as file:
        file.write(get_example_expedition())
    return Expedition.from_yaml(tmp_file).ship_config


@pytest.fixture
def ship_config_no_xbt(ship_config):
    delattr(ship_config, "xbt_config")
    return ship_config


@pytest.fixture
def ship_config_no_ctd(ship_config):
    delattr(ship_config, "ctd_config")
    return ship_config


@pytest.fixture
def ship_config_no_ctd_bgc(ship_config):
    delattr(ship_config, "ctd_bgc_config")
    return ship_config


@pytest.fixture
def ship_config_no_argo_float(ship_config):
    delattr(ship_config, "argo_float_config")
    return ship_config


@pytest.fixture
def ship_config_no_drifter(ship_config):
    delattr(ship_config, "drifter_config")
    return ship_config


def test_verify_ship_config(ship_config, schedule) -> None:
    ship_config.verify(schedule)


def test_verify_ship_config_no_instrument(ship_config, schedule_no_xbt) -> None:
    ship_config.verify(schedule_no_xbt)


@pytest.mark.parametrize(
    "ship_config_fixture,error,match",
    [
        pytest.param(
            "ship_config_no_xbt",
            ConfigError,
            "Schedule includes instrument 'XBT', but ship_config does not provide configuration for it.",
            id="ShipConfigNoXBT",
        ),
        pytest.param(
            "ship_config_no_ctd",
            ConfigError,
            "Schedule includes instrument 'CTD', but ship_config does not provide configuration for it.",
            id="ShipConfigNoCTD",
        ),
        pytest.param(
            "ship_config_no_ctd_bgc",
            ConfigError,
            "Schedule includes instrument 'CTD_BGC', but ship_config does not provide configuration for it.",
            id="ShipConfigNoCTD_BGC",
        ),
        pytest.param(
            "ship_config_no_argo_float",
            ConfigError,
            "Schedule includes instrument 'ARGO_FLOAT', but ship_config does not provide configuration for it.",
            id="ShipConfigNoARGO_FLOAT",
        ),
        pytest.param(
            "ship_config_no_drifter",
            ConfigError,
            "Schedule includes instrument 'DRIFTER', but ship_config does not provide configuration for it.",
            id="ShipConfigNoDRIFTER",
        ),
    ],
)
def test_verify_ship_config_errors(
    request, schedule, ship_config_fixture, error, match
) -> None:
    ship_config = request.getfixturevalue(ship_config_fixture)

    with pytest.raises(error, match=match):
        ship_config.verify(schedule)
