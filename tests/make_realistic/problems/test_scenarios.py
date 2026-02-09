from dataclasses import is_dataclass
from datetime import timedelta

from virtualship.instruments.types import InstrumentType
from virtualship.make_realistic.problems.scenarios import (
    GENERAL_PROBLEMS,
    INSTRUMENT_PROBLEMS,
    GeneralProblem,
    InstrumentProblem,
)


def _assert_general_problem_class(cls):
    assert isinstance(cls, GeneralProblem)
    instance = cls()
    assert is_dataclass(instance)

    # required attributes and types
    assert isinstance(instance.message, str)
    assert instance.message.strip(), "message should not be empty"

    assert isinstance(instance.delay_duration, timedelta)
    assert isinstance(instance.pre_departure, bool)


def _assert_instrument_problem_class(cls):
    assert isinstance(cls, InstrumentProblem)
    instance = cls()
    assert is_dataclass(instance)

    # required attributes and types
    assert isinstance(instance.message, str)
    assert instance.message.strip(), "message should not be empty"

    assert isinstance(instance.delay_duration, timedelta)
    assert isinstance(instance.instrument_type, InstrumentType)


def test_general_problems():
    assert GENERAL_PROBLEMS, "GENERAL_PROBLEMS should not be empty"

    for cls in GENERAL_PROBLEMS:
        _assert_general_problem_class(cls)


def test_instrument_problems():
    assert INSTRUMENT_PROBLEMS, "INSTRUMENT_PROBLEMS should not be empty"

    for cls in INSTRUMENT_PROBLEMS:
        _assert_instrument_problem_class(cls)
