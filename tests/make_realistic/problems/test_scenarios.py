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

    # required attributes and types
    assert isinstance(cls.message, str)
    assert cls.message.strip(), "message should not be empty"

    assert isinstance(cls.delay_duration, timedelta)
    assert isinstance(cls.pre_departure, bool)


def _assert_instrument_problem_class(cls):
    assert isinstance(cls, InstrumentProblem)

    # required attributes and types
    assert isinstance(cls.message, str)
    assert cls.message.strip(), "message should not be empty"

    assert isinstance(cls.delay_duration, timedelta)
    assert isinstance(cls.instrument_type, InstrumentType)


def test_general_problems():
    assert GENERAL_PROBLEMS, "GENERAL_PROBLEMS should not be empty"

    for cls in GENERAL_PROBLEMS:
        _assert_general_problem_class(cls)


def test_instrument_problems():
    assert INSTRUMENT_PROBLEMS, "INSTRUMENT_PROBLEMS should not be empty"

    for cls in INSTRUMENT_PROBLEMS:
        _assert_instrument_problem_class(cls)
