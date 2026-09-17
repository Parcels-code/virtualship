import json
from datetime import datetime
from pathlib import Path

import pytest

from virtualship.models.checkpoint import Checkpoint
from virtualship.models.expedition import Expedition, Port, Schedule, Waypoint
from virtualship.models.location import Location
from virtualship.utils import _get_example_expedition


@pytest.fixture
def expedition(tmp_file):
    with open(tmp_file, "w") as file:
        file.write(_get_example_expedition())

    return Expedition.from_yaml(tmp_file)


def make_dummy_checkpoint(problem_wp_i=None):
    departure_port = Port(
        location=Location(-1.0, 0.0), time=datetime(2024, 2, 1, 8, 0, 0)
    )
    wp1 = Waypoint(
        location=Location(latitude=0.0, longitude=0.0),
        time=datetime(2024, 2, 1, 10, 0, 0),
        instrument=[],
    )
    wp2 = Waypoint(
        location=Location(latitude=1.0, longitude=1.0),
        time=datetime(2024, 2, 1, 12, 0, 0),
        instrument=[],
    )
    arrival_port = Port(location=Location(2.0, 0.0), time=datetime(2024, 2, 1, 8, 0, 0))

    schedule = Schedule(waypoints=[departure_port, wp1, wp2, arrival_port])
    return Checkpoint(past_schedule=schedule, problem_wp_i=problem_wp_i)


def test_to_and_from_yaml(tmp_path):
    cp = make_dummy_checkpoint()
    file_path = tmp_path / "checkpoint.yaml"
    cp.to_yaml(file_path)
    loaded = Checkpoint.from_yaml(file_path)

    assert isinstance(loaded, Checkpoint)
    assert loaded.past_schedule.waypoints[0].time == cp.past_schedule.waypoints[0].time


def test_verify_no_problems_encountered(expedition):
    """With an empty problems dir, verify() should not raise, regardless of problem_wp_i."""
    cp = make_dummy_checkpoint(problem_wp_i=1)
    expedition.schedule = cp.past_schedule
    cp.verify(expedition, Path("/tmp/empty"))  # should not raise errors


def test_verify_past_waypoints_changed(expedition):
    cp = make_dummy_checkpoint(problem_wp_i=1)
    expedition.schedule = cp.past_schedule

    # change a past waypoint (waypoint 1, which is within the protected prefix for problem_wp_i=1)
    new_wp1 = Waypoint(
        location=Location(latitude=0.0, longitude=0.0),
        time=datetime(2024, 2, 1, 11, 0, 0),
        instrument=None,
    )
    new_schedule = Schedule(
        waypoints=[
            cp.past_schedule.waypoints[0],
            new_wp1,
            cp.past_schedule.waypoints[2],
            cp.past_schedule.waypoints[-1],
        ]
    )
    expedition.schedule = new_schedule

    with pytest.raises(Exception) as excinfo:
        cp.verify(expedition, Path("/tmp/empty"))
    assert "Past waypoints in schedule have been changed" in str(excinfo.value)


@pytest.mark.parametrize(
    "delay_duration_hours, should_resolve",
    [
        (1.0, True),  # problem resolved
        (5.0, False),  # problem unresolved
    ],
)
def test_verify_problem_resolution(
    tmp_path,
    expedition,
    delay_duration_hours,
    should_resolve,
):
    # departure port is active, so it is itself the problem waypoint (problem_wp_i=0);
    # locations are kept very close together so sail time is negligible and the test
    # isolates the delay-vs-buffer comparison.
    departure_port = Port(
        location=Location(0.0, 0.0), time=datetime(2024, 2, 1, 8, 0, 0)
    )
    wp1 = Waypoint(
        location=Location(latitude=0.0, longitude=0.001),
        time=datetime(2024, 2, 1, 10, 0, 0),
        instrument=[],
    )
    arrival_port = Port(
        location=Location(0.0, 0.002), time=datetime(2024, 2, 1, 12, 0, 0)
    )
    past_schedule = Schedule(waypoints=[departure_port, wp1, arrival_port])
    cp = Checkpoint(past_schedule=past_schedule, problem_wp_i=0)

    # new schedule: push wp1 back by 1 hour (departure port must stay unchanged, as it
    # is before the failed waypoint)
    new_wp1 = Waypoint(
        location=wp1.location,
        time=datetime(2024, 2, 1, 11, 0, 0),
        instrument=[],
    )
    new_arrival_port = Port(
        location=arrival_port.location, time=datetime(2024, 2, 1, 13, 0, 0)
    )
    new_schedule = Schedule(waypoints=[departure_port, new_wp1, new_arrival_port])
    expedition.schedule = new_schedule

    # unresolved problem file
    problem = {
        "resolved": False,
        "delay_duration_hours": delay_duration_hours,
        "problem_wp_i": 0,
    }
    problem_file = tmp_path / "problem_1.json"
    with open(problem_file, "w") as f:
        json.dump(problem, f)

    # check if resolution is detected correctly
    if should_resolve:
        cp.verify(expedition, tmp_path)
        with open(problem_file) as f:
            updated = json.load(f)
        assert updated["resolved"] is True
    else:
        with pytest.raises(Exception) as excinfo:
            cp.verify(expedition, tmp_path)
        assert "has not been resolved in the schedule" in str(excinfo.value)


@pytest.mark.parametrize(
    "delay_duration_hours, should_resolve",
    [
        (1.0, True),  # pushing wp1 back by 2h absorbs a 1h delay
        (5.0, False),  # pushing wp1 back by 2h does not absorb a 5h delay
    ],
)
def test_verify_problem_resolution_pre_departure_no_active_port(
    tmp_path,
    expedition,
    delay_duration_hours,
    should_resolve,
):
    """problem_wp_i is None for a pre-departure problem with no active departure port."""
    departure_port = Port()  # inactive placeholder: no location/time
    wp1 = Waypoint(
        location=Location(latitude=0.0, longitude=0.0),
        time=datetime(2024, 2, 1, 10, 0, 0),
        instrument=[],
    )
    wp2 = Waypoint(
        location=Location(latitude=1.0, longitude=1.0),
        time=datetime(2024, 2, 1, 12, 0, 0),
        instrument=[],
    )
    arrival_port = Port(
        location=Location(2.0, 0.0), time=datetime(2024, 2, 1, 14, 0, 0)
    )

    past_schedule = Schedule(waypoints=[departure_port, wp1, wp2, arrival_port])
    cp = Checkpoint(past_schedule=past_schedule, problem_wp_i=None)

    # new schedule: push wp1 (and everything after it) back by 2 hours
    new_wp1 = Waypoint(
        location=wp1.location,
        time=datetime(2024, 2, 1, 12, 0, 0),
        instrument=[],
    )
    new_wp2 = Waypoint(
        location=wp2.location,
        time=datetime(2024, 2, 1, 14, 0, 0),
        instrument=[],
    )
    new_schedule = Schedule(waypoints=[departure_port, new_wp1, new_wp2, arrival_port])
    expedition.schedule = new_schedule

    problem = {
        "resolved": False,
        "delay_duration_hours": delay_duration_hours,
        "problem_wp_i": None,
    }
    problem_file = tmp_path / "problem_1.json"
    with open(problem_file, "w") as f:
        json.dump(problem, f)

    if should_resolve:
        cp.verify(expedition, tmp_path)
        with open(problem_file) as f:
            updated = json.load(f)
        assert updated["resolved"] is True
    else:
        with pytest.raises(Exception) as excinfo:
            cp.verify(expedition, tmp_path)
        assert "has not been resolved in the schedule" in str(excinfo.value)
