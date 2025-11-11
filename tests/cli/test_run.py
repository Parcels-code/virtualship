from pathlib import Path

from pytest import CaptureFixture

from virtualship.cli import _run


def test_run(capfd: CaptureFixture) -> None:
    _run("expedition_dir", input_data=Path("expedition_dir/input_data"))
    out, _ = capfd.readouterr()
    assert "Your expedition has concluded successfully!" in out, (
        "Expedition did not complete successfully."
    )
