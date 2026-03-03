from datetime import datetime, timedelta

import numpy as np
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
    assert instruments_config.ctd_config.stationkeeping_time == timedelta(minutes=50)
    assert instruments_config.ctd_bgc_config.stationkeeping_time == timedelta(
        minutes=50
    )
    assert instruments_config.argo_float_config.stationkeeping_time == timedelta(
        minutes=20
    )
    assert instruments_config.drifter_config.stationkeeping_time == timedelta(
        minutes=20
    )
    assert instruments_config.ship_underwater_st_config.period == timedelta(minutes=5)


def test_ship_path_inside_domain() -> None:
    """Test that the ship path (here represented by underway ADCP measurement sites) is inside the domain defined by the waypoints (which determines the fieldset bounds)."""
    base_time = datetime.strptime("2022-01-01T00:00:00", "%Y-%m-%dT%H:%M:%S")

    projection = pyproj.Geod(ellps="WGS84")
    expedition = Expedition.from_yaml("expedition_dir/expedition.yaml")
    expedition.ship_config.ship_speed_knots = 10.0

    wp1 = Location(-63.0, -57.7)  # most southern
    wp2 = Location(-55.4, -66.2)  # most northern
    wp3 = Location(-61.8, -73.2)  # most western
    wp4 = Location(-57.3, -51.8)  # most eastern

    # waypoints with enough distance where curvature is clear
    expedition.schedule = Schedule(
        waypoints=[
            Waypoint(location=wp1, time=base_time),
            Waypoint(location=wp2, time=base_time + timedelta(days=5)),
            Waypoint(location=wp3, time=base_time + timedelta(days=10)),
            Waypoint(location=wp4, time=base_time + timedelta(days=15)),
        ]
    )

    # get waypoint domain bounds
    wp_max_lat, wp_min_lat, wp_max_lon, wp_min_lon = (
        max(wp.location.lat for wp in expedition.schedule.waypoints),
        min(wp.location.lat for wp in expedition.schedule.waypoints),
        max(wp.location.lon for wp in expedition.schedule.waypoints),
        min(wp.location.lon for wp in expedition.schedule.waypoints),
    )

    result = simulate_schedule(projection, expedition)
    assert isinstance(result, ScheduleOk)

    # adcp measurements path
    adcp_measurements = result.measurements_to_simulate.adcps
    adcp_lats = [m.location.lat for m in adcp_measurements]
    adcp_lons = [m.location.lon for m in adcp_measurements]

    adcp_max_lat, adcp_min_lat, adcp_max_lon, adcp_min_lon = (
        max(adcp_lats),
        min(adcp_lats),
        max(adcp_lons),
        min(adcp_lons),
    )

    # check adcp route is within wp bounds
    assert adcp_max_lat <= wp_max_lat
    assert adcp_min_lat >= wp_min_lat
    assert adcp_max_lon <= wp_max_lon
    assert adcp_min_lon >= wp_min_lon

    # the adcp route extremes should also approximately match waypoints defined in this test
    assert np.isclose(adcp_max_lat, wp2.lat, atol=0.1)
    assert np.isclose(adcp_min_lat, wp1.lat, atol=0.1)
    assert np.isclose(adcp_max_lon, wp4.lon, atol=0.1)
    assert np.isclose(adcp_min_lon, wp3.lon, atol=0.1)
