from pathlib import Path

import numpy as np
import pytest
import xarray as xr
from click.testing import CliRunner

from virtualship.cli.commands import init
from virtualship.utils import EXPEDITION


@pytest.fixture
def copernicus_no_download(monkeypatch):
    """Mock the copernicusmarine `subset` and `open_dataset` functions, approximating the reanalysis products."""

    # mock for copernicusmarine.subset
    def fake_download(output_filename, output_directory, **_):
        Path(output_directory).joinpath(output_filename).touch()

    def fake_open_dataset(*args, **kwargs):
        return xr.Dataset(
            coords={
                "time": (
                    "time",
                    [
                        np.datetime64("2022-01-01"),
                        np.datetime64("2025-01-01"),
                    ],  # mock up rough reanalysis period, covers test schedule
                )
            }
        )

    monkeypatch.setattr("virtualship.cli._fetch.copernicusmarine.subset", fake_download)
    monkeypatch.setattr(
        "virtualship.cli._fetch.copernicusmarine.open_dataset", fake_open_dataset
    )
    yield


@pytest.fixture
def runner():
    """An example expedition."""
    runner = CliRunner()
    with runner.isolated_filesystem():
        runner.invoke(init, ["."])
        yield runner


def test_init():
    runner = CliRunner()
    with runner.isolated_filesystem():
        result = runner.invoke(init, ["."])
        assert result.exit_code == 0
        expedition = Path(EXPEDITION)

        assert expedition.exists()


def test_init_existing_expedition():
    runner = CliRunner()
    with runner.isolated_filesystem():
        expedition = Path(EXPEDITION)
        expedition.write_text("test")

        with pytest.raises(FileExistsError):
            result = runner.invoke(init, ["."])
            raise result.exception
