from pathlib import Path

from pytest import CaptureFixture

from virtualship.expedition import do_expedition


def test_do_expedition(capfd: CaptureFixture) -> None:
    do_expedition("expedition_dir", input_data=Path("expedition_dir/input_data"))
    out, _ = capfd.readouterr()
    assert "Your expedition has concluded successfully!" in out, (
        "Expedition did not complete successfully."
    )
