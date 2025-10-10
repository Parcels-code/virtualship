from datetime import datetime, timedelta
from pathlib import Path

import pyproj
import pytest

from virtualship.errors import ScheduleError
from virtualship.expedition.do_expedition import _load_input_data
from virtualship.models import Location, Schedule, Waypoint
from virtualship.utils import _get_ship_config

projection = pyproj.Geod(ellps="WGS84")

expedition_dir = Path("expedition_dir")


def test_import_export_schedule(tmpdir) -> None:
    out_path = tmpdir.join("schedule.yaml")

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
    schedule.to_yaml(out_path)

    schedule2 = Schedule.from_yaml(out_path)
    assert schedule == schedule2


def test_verify_schedule() -> None:
    schedule = Schedule(
        waypoints=[
            Waypoint(location=Location(0, 0), time=datetime(2022, 1, 1, 1, 0, 0)),
            Waypoint(location=Location(1, 0), time=datetime(2022, 1, 2, 1, 0, 0)),
        ]
    )

    ship_config = _get_ship_config(expedition_dir)

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
    ship_config = _get_ship_config(expedition_dir)

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
