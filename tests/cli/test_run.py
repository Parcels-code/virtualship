from datetime import datetime
from pathlib import Path
from unittest.mock import MagicMock

import pytest

from virtualship.cli._run import _run, _unique_id
from virtualship.expedition.simulate_schedule import (
    MeasurementsToSimulate,
    ScheduleOk,
)
from virtualship.instruments.types import InstrumentType
from virtualship.utils import EXPEDITION, EXPEDITION_IDENTIFIER, get_example_expedition


def _simulate_schedule(projection, expedition):
    """Return a trivial ScheduleOk with no measurements to simulate."""
    return ScheduleOk(
        time=datetime.now(), measurements_to_simulate=MeasurementsToSimulate()
    )


class DummyInstrument:
    """Dummy instrument class that just creates empty output directories."""

    def __init__(self, expedition, from_data=None):
        """Initialize DummyInstrument."""
        self.expedition = expedition
        self.from_data = from_data

    def execute(self, measurements, out_path):
        """Mock execute method."""
        out_path = Path(out_path)
        out_path.parent.mkdir(parents=True, exist_ok=True)
        out_path.mkdir(parents=True, exist_ok=True)


def test_run(tmp_path, monkeypatch):
    """Testing as if using pre-downloaded, local data."""
    difficulty_level = "easy"

    expedition_dir = tmp_path / "expedition_dir"
    expedition_dir.mkdir()
    (expedition_dir / EXPEDITION).write_text(get_example_expedition())

    monkeypatch.setattr("virtualship.cli._run.simulate_schedule", _simulate_schedule)

    monkeypatch.setattr(
        "virtualship.models.InstrumentsConfig.verify", lambda self, expedition: None
    )
    monkeypatch.setattr(
        "virtualship.models.Schedule.verify", lambda self, *args, **kwargs: None
    )

    monkeypatch.setattr(
        "virtualship.cli._run.get_instrument_class", lambda itype: DummyInstrument
    )

    fake_data_dir = tmp_path / "fake_data"
    fake_data_dir.mkdir()

    _run(
        expedition_dir, difficulty_level=difficulty_level, from_data=fake_data_dir
    )  # problems turned off here

    results_dir = expedition_dir / "results"

    assert results_dir.exists() and results_dir.is_dir()
    cost_file = results_dir / "cost.txt"
    assert cost_file.exists()
    content = cost_file.read_text()
    assert "cost:" in content

    # check cache dir is deleted at end of expedition when difficulty-level is easy
    if difficulty_level == "easy":
        cache_dir = expedition_dir / "cache"
        assert not cache_dir.exists()


# ---------------------------------------------------------------------------
# Unit tests for _unique_id
# ---------------------------------------------------------------------------


@pytest.mark.parametrize("difficulty_level", ["easy", "hard", "medium"])
def test_unique_id_incomplete_cache_does_not_raise(tmp_path, difficulty_level):
    """When expedition_latest.yaml is missing (incomplete cache from an interrupted run), _unique_id must not raise error for any 'difficulty_level', it should return a new id."""
    ORIGINAL_TIMESTAMP = "20240101120000"

    cache_dir = tmp_path / "cache"
    cache_dir.mkdir()
    (cache_dir / EXPEDITION_IDENTIFIER).write_text(ORIGINAL_TIMESTAMP)
    # EXPEDITION_LATEST intentionally absent to simulate an interrupted run

    expedition = MagicMock()
    expedition.get_instruments.return_value = {InstrumentType.CTD}

    result = _unique_id(expedition, cache_dir, difficulty_level=difficulty_level)

    assert result != ORIGINAL_TIMESTAMP
    assert (
        abs(datetime.strptime(result, "%Y%m%d%H%M%S") - datetime.now()).seconds < 30
    ), "new ID should be timestamp close to the current time"
    assert (cache_dir / EXPEDITION_IDENTIFIER).read_text().strip() == result
