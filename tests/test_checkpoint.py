import json
from datetime import datetime, timedelta
from pathlib import Path
from unittest.mock import patch

import pytest

from virtualship.models.checkpoint import Checkpoint
from virtualship.models.expedition import Expedition, Schedule, Waypoint
from virtualship.models.location import Location
from virtualship.utils import get_example_expedition


@pytest.fixture
def expedition(tmp_file):
    with open(tmp_file, "w") as file:
        file.write(get_example_expedition())
    return Expedition.from_yaml(tmp_file)


def make_dummy_checkpoint(failed_waypoint_i=None):
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

    schedule = Schedule(waypoints=[wp1, wp2])
    return Checkpoint(past_schedule=schedule, failed_waypoint_i=failed_waypoint_i)


def test_to_and_from_yaml(tmp_path):
    cp = make_dummy_checkpoint()
    file_path = tmp_path / "checkpoint.yaml"
    cp.to_yaml(file_path)
    loaded = Checkpoint.from_yaml(file_path)

    assert isinstance(loaded, Checkpoint)
    assert loaded.past_schedule.waypoints[0].time == cp.past_schedule.waypoints[0].time


def test_verify_no_failed_waypoint(expedition):
    cp = make_dummy_checkpoint(failed_waypoint_i=None)
    cp.verify(expedition, Path("/tmp/empty"))  # should not raise errors


def test_verify_past_waypoints_changed(expedition):
    cp = make_dummy_checkpoint(failed_waypoint_i=1)

    # change past waypoints
    new_wp1 = Waypoint(
        location=Location(latitude=0.0, longitude=0.0),
        time=datetime(2024, 2, 1, 11, 0, 0),
        instrument=None,
    )
    new_wp2 = Waypoint(
        location=Location(latitude=1.0, longitude=1.0),
        time=datetime(2024, 2, 1, 12, 0, 0),
        instrument=None,
    )
    new_schedule = Schedule(waypoints=[new_wp1, new_wp2])
    expedition.schedule = new_schedule

    with pytest.raises(Exception) as excinfo:
        cp.verify(expedition, Path("/tmp/empty"))
    assert "Past waypoints in schedule have been changed" in str(excinfo.value)


@pytest.mark.parametrize(
    "delay_duration_hours, new_wp2_time, should_resolve",
    [
        (1.0, datetime(2024, 2, 1, 15, 0, 0), True),  # problem resolved
        (5.0, datetime(2024, 2, 1, 12, 0, 0), False),  # problem unresolved
    ],
)
@patch(
    "virtualship.models.checkpoint._calc_wp_stationkeeping_time",
    return_value=timedelta(hours=1),
)
@patch(
    "virtualship.models.checkpoint._calc_sail_time",
    return_value=(timedelta(hours=2), None),
)
def test_verify_problem_resolution(
    mock_sail,
    mock_stationkeeping,
    tmp_path,
    expedition,
    delay_duration_hours,
    new_wp2_time,
    should_resolve,
):
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
    past_schedule = Schedule(waypoints=[wp1, wp2])
    cp = Checkpoint(past_schedule=past_schedule, failed_waypoint_i=1)

    # new schedule
    new_wp1 = Waypoint(
        location=Location(latitude=0.0, longitude=0.0),
        time=datetime(2024, 2, 1, 10, 0, 0),
        instrument=[],
    )
    new_wp2 = Waypoint(
        location=Location(latitude=1.0, longitude=1.0),
        time=new_wp2_time,
        instrument=[],
    )
    new_schedule = Schedule(waypoints=[new_wp1, new_wp2])
    expedition.schedule = new_schedule

    # unresolved problem file
    problems_dir = tmp_path
    problem = {
        "resolved": False,
        "delay_duration_hours": delay_duration_hours,
        "problem_waypoint_i": 0,
    }
    problem_file = problems_dir / "problem_1.json"
    with open(problem_file, "w") as f:
        json.dump(problem, f)

    # check if resolution is detected correctly
    if should_resolve:
        cp.verify(expedition, problems_dir)
        with open(problem_file) as f:
            updated = json.load(f)
        assert updated["resolved"] is True
    else:
        with pytest.raises(Exception) as excinfo:
            cp.verify(expedition, problems_dir)
        assert "has not been resolved in the schedule" in str(excinfo.value)
