from datetime import datetime
from pathlib import Path

from virtualship.cli._run import _run
from virtualship.expedition.simulate_schedule import (
    MeasurementsToSimulate,
    ScheduleOk,
)
from virtualship.utils import EXPEDITION, get_example_expedition


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

    _run(expedition_dir, from_data=fake_data_dir)

    results_dir = expedition_dir / "results"

    assert results_dir.exists() and results_dir.is_dir()
    cost_file = results_dir / "cost.txt"
    assert cost_file.exists()
    content = cost_file.read_text()
    assert "cost:" in content
