from datetime import datetime, timedelta

import pyproj

from virtualship.expedition.simulate_schedule import (
    ScheduleOk,
    ScheduleProblem,
    simulate_schedule,
)
from virtualship.models import Expedition, Location, Schedule, Waypoint


def test_simulate_schedule_feasible() -> None:
    """Test schedule with two waypoints that can be reached within time is OK."""
    base_time = datetime.strptime("2022-01-01T00:00:00", "%Y-%m-%dT%H:%M:%S")

    projection = pyproj.Geod(ellps="WGS84")
    expedition = Expedition.from_yaml("expedition_dir/expedition.yaml")
    expedition.ship_config.ship_speed_knots = 10.0
    expedition.schedule = Schedule(
        waypoints=[
            Waypoint(location=Location(0, 0), time=base_time),
            Waypoint(location=Location(0.01, 0), time=base_time + timedelta(days=1)),
        ]
    )

    result = simulate_schedule(projection, expedition)

    assert isinstance(result, ScheduleOk)


def test_simulate_schedule_too_far() -> None:
    """Test schedule with two waypoints that are very far away and cannot be reached in time is not OK."""
    base_time = datetime.strptime("2022-01-01T00:00:00", "%Y-%m-%dT%H:%M:%S")

    projection = pyproj.Geod(ellps="WGS84")
    expedition = Expedition.from_yaml("expedition_dir/expedition.yaml")
    expedition.ship_config.ship_speed_knots = 10.0
    expedition.schedule = Schedule(
        waypoints=[
            Waypoint(location=Location(0, 0), time=base_time),
            Waypoint(location=Location(1.0, 0), time=base_time + timedelta(minutes=1)),
        ]
    )

    result = simulate_schedule(projection, expedition)

    assert isinstance(result, ScheduleProblem)


def test_time_in_minutes_in_ship_schedule() -> None:
    """Test whether the pydantic serializer picks up the time *in minutes* in the ship schedule."""
    instruments_config = Expedition.from_yaml(
        "expedition_dir/expedition.yaml"
    ).instruments_config
    assert instruments_config.adcp_config.period == timedelta(minutes=5)
    assert instruments_config.ctd_config.stationkeeping_time == timedelta(minutes=35)
    assert instruments_config.ctd_bgc_config.stationkeeping_time == timedelta(
        minutes=35
    )
    assert instruments_config.ship_underwater_st_config.period == timedelta(minutes=5)
