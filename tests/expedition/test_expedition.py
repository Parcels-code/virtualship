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

    schedule.verify(ship_speed_knots, None)


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
    expedition = _get_expedition(expedition_dir)
    input_data = _load_input_data(
        expedition_dir,
        expedition,
        input_data=Path("expedition_dir/input_data"),
    )

    with pytest.raises(error, match=match):
        schedule.verify(
            expedition.ship_config.ship_speed_knots,
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
def instruments_config(tmp_file):
    with open(tmp_file, "w") as file:
        file.write(get_example_expedition())
    return Expedition.from_yaml(tmp_file).instruments_config


@pytest.fixture
def instruments_config_no_xbt(instruments_config):
    delattr(instruments_config, "xbt_config")
    return instruments_config


@pytest.fixture
def instruments_config_no_ctd(instruments_config):
    delattr(instruments_config, "ctd_config")
    return instruments_config


@pytest.fixture
def instruments_config_no_ctd_bgc(instruments_config):
    delattr(instruments_config, "ctd_bgc_config")
    return instruments_config


@pytest.fixture
def instruments_config_no_argo_float(instruments_config):
    delattr(instruments_config, "argo_float_config")
    return instruments_config


@pytest.fixture
def instruments_config_no_drifter(instruments_config):
    delattr(instruments_config, "drifter_config")
    return instruments_config


def test_verify_instruments_config(instruments_config, schedule) -> None:
    instruments_config.verify(schedule)


def test_verify_instruments_config_no_instrument(
    instruments_config, schedule_no_xbt
) -> None:
    instruments_config.verify(schedule_no_xbt)


@pytest.mark.parametrize(
    "instruments_config_fixture,error,match",
    [
        pytest.param(
            "instruments_config_no_xbt",
            ConfigError,
            "Schedule includes instrument 'XBT', but instruments_config does not provide configuration for it.",
            id="ShipConfigNoXBT",
        ),
        pytest.param(
            "instruments_config_no_ctd",
            ConfigError,
            "Schedule includes instrument 'CTD', but instruments_config does not provide configuration for it.",
            id="ShipConfigNoCTD",
        ),
        pytest.param(
            "instruments_config_no_ctd_bgc",
            ConfigError,
            "Schedule includes instrument 'CTD_BGC', but instruments_config does not provide configuration for it.",
            id="ShipConfigNoCTD_BGC",
        ),
        pytest.param(
            "instruments_config_no_argo_float",
            ConfigError,
            "Schedule includes instrument 'ARGO_FLOAT', but instruments_config does not provide configuration for it.",
            id="ShipConfigNoARGO_FLOAT",
        ),
        pytest.param(
            "instruments_config_no_drifter",
            ConfigError,
            "Schedule includes instrument 'DRIFTER', but instruments_config does not provide configuration for it.",
            id="ShipConfigNoDRIFTER",
        ),
    ],
)
def test_verify_instruments_config_errors(
    request, schedule, instruments_config_fixture, error, match
) -> None:
    instruments_config = request.getfixturevalue(instruments_config_fixture)

    with pytest.raises(error, match=match):
        instruments_config.verify(schedule)
