import json
from datetime import datetime, timedelta

from virtualship.make_realistic.problems.scenarios import GeneralProblem
from virtualship.make_realistic.problems.simulator import ProblemSimulator
from virtualship.models.expedition import (
    Expedition,
    InstrumentsConfig,
    Schedule,
    ShipConfig,
    Waypoint,
)
from virtualship.models.location import Location
from virtualship.utils import GENERAL_PROBLEM_REG


def _make_simple_expedition(
    num_waypoints: int = 2, distance_scale: float = 1.0
) -> Expedition:
    sample_datetime = datetime(2024, 1, 1, 0, 0, 0)
    waypoints = []
    for i in range(num_waypoints):
        wp = Waypoint(
            location=Location(
                latitude=0.0 + i * distance_scale, longitude=0.0 + i * distance_scale
            ),
            time=sample_datetime + timedelta(days=i),
            instrument=[],  # ensure is list, not None
        )
        waypoints.append(wp)

    schedule = Schedule(waypoints=waypoints)
    instruments = InstrumentsConfig()
    ship = ShipConfig(ship_speed_knots=10.0)
    return Expedition(
        schedule=schedule, instruments_config=instruments, ship_config=ship
    )


def test_select_problems_single_waypoint_returns_pre_departure(tmp_path):
    expedition = _make_simple_expedition(num_waypoints=1)
    simulator = ProblemSimulator(expedition, str(tmp_path))
    problems = simulator.select_problems(set(), prob_level=2)

    assert isinstance(problems, dict)
    assert len(problems["problem_class"]) == 1
    assert problems["waypoint_i"] == [None]

    problem_cls = problems["problem_class"][0]
    assert issubclass(problem_cls, GeneralProblem)
    assert getattr(problem_cls, "pre_departure", False) is True


def test_select_problems_prob_level_zero():
    expedition = _make_simple_expedition(num_waypoints=2)
    simulator = ProblemSimulator(expedition, ".")

    problems = simulator.select_problems(set(), prob_level=0)
    assert problems is None


def test_cache_and_load_selected_problems_roundtrip(tmp_path):
    expedition = _make_simple_expedition(num_waypoints=2)
    simulator = ProblemSimulator(expedition, str(tmp_path))

    # pick two general problems (registry should contain entries)
    cls1 = GENERAL_PROBLEM_REG[0]
    cls2 = GENERAL_PROBLEM_REG[1] if len(GENERAL_PROBLEM_REG) > 1 else cls1

    problems = {"problem_class": [cls1, cls2], "waypoint_i": [None, 0]}

    sel_fpath = tmp_path / "subdir" / "selected_problems.json"
    simulator.cache_selected_problems(problems, str(sel_fpath))

    assert sel_fpath.exists()
    with open(sel_fpath, encoding="utf-8") as f:
        data = json.load(f)
    assert "problem_class" in data and "waypoint_i" in data

    # now load via simulator, verify class names map back to original selected problem classes
    loaded = simulator.load_selected_problems(str(sel_fpath))
    assert loaded["waypoint_i"] == problems["waypoint_i"]
    assert [c.__name__ for c in problems["problem_class"]] == [
        c.__name__ for c in loaded["problem_class"]
    ]


def test_hash_to_json(tmp_path):
    expedition = _make_simple_expedition(num_waypoints=2)
    simulator = ProblemSimulator(expedition, str(tmp_path))

    cls = GENERAL_PROBLEM_REG[0]

    hash_path = tmp_path / "problem_hash.json"
    simulator._hash_to_json(
        cls, "deadbeef", None, hash_path
    )  # "deadbeef" as sub for hex in test

    assert hash_path.exists()
    with open(hash_path, encoding="utf-8") as f:
        obj = json.load(f)
    assert obj["problem_hash"] == "deadbeef"
    assert "message" in obj and "delay_duration_hours" in obj
    assert obj["resolved"] is False


def test_has_contingency_pre_departure(tmp_path):
    expedition = _make_simple_expedition(num_waypoints=2)
    simulator = ProblemSimulator(expedition, str(tmp_path))
    cls = GENERAL_PROBLEM_REG[0]

    # _has_contingency should return False for pre-departure (None)
    assert simulator._has_contingency(cls, None) is False


def test_select_problems_prob_levels(tmp_path):
    expedition = _make_simple_expedition(num_waypoints=3)
    simulator = ProblemSimulator(expedition, str(tmp_path))

    for level in range(3):  # prob levels 0, 1, 2
        problems = simulator.select_problems(set(), prob_level=level)
        if level == 0:
            assert problems is None
        else:
            assert isinstance(problems, dict)
            assert len(problems["problem_class"]) > 0
            assert len(problems["waypoint_i"]) == len(problems["problem_class"])
            if level == 1:
                assert len(problems["problem_class"]) <= 2


def test_prob_level_two_more_problems(tmp_path):
    prob_level = 2

    short_expedition = _make_simple_expedition(num_waypoints=2)
    simulator_short = ProblemSimulator(short_expedition, str(tmp_path))
    long_expedition = _make_simple_expedition(num_waypoints=12)
    simulator_long = ProblemSimulator(long_expedition, str(tmp_path))

    problems_short = simulator_short.select_problems(set(), prob_level=prob_level)
    problems_long = simulator_long.select_problems(set(), prob_level=prob_level)

    assert len(problems_long["problem_class"]) >= len(
        problems_short["problem_class"]
    ), "Longer expedition should have more problems than shorter one at prob_level=2"


def test_has_contingency_during_expedition(tmp_path):
    # expedition with long distance between waypoints
    long_wp_expedition = _make_simple_expedition(num_waypoints=2, distance_scale=3.0)
    long_simulator = ProblemSimulator(long_wp_expedition, str(tmp_path))
    # short distance
    short_wp_expedition = _make_simple_expedition(num_waypoints=2, distance_scale=0.01)
    short_simulator = ProblemSimulator(short_wp_expedition, str(tmp_path))

    # a during-expedition general problem
    problem_cls = next(
        c for c in GENERAL_PROBLEM_REG if not getattr(c, "pre_departure", False)
    )

    assert problem_cls is not None, (
        "Need at least one non-pre-departure problem class in the general problem registry"
    )

    # short distance expedition should have contingency, long distance should not (given time between waypoints and ship speed is constant)
    assert short_simulator._has_contingency(problem_cls, problem_waypoint_i=0) is True
    assert long_simulator._has_contingency(problem_cls, problem_waypoint_i=0) is False
