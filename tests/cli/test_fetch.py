from pathlib import Path

import numpy as np
import pytest
import xarray as xr
from pydantic import BaseModel

from virtualship.cli._fetch import (
    DOWNLOAD_METADATA,
    DownloadMetadata,
    IncompleteDownloadError,
    _fetch,
    assert_complete_download,
    complete_download,
    create_hash,
    filename_to_hash,
    get_existing_download,
    hash_model,
    hash_to_filename,
)
from virtualship.models import Expedition
from virtualship.utils import EXPEDITION, get_example_expedition


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
                    ],  # mock up rough renanalysis period
                )
            }
        )

    monkeypatch.setattr("virtualship.cli._fetch.copernicusmarine.subset", fake_download)
    monkeypatch.setattr(
        "virtualship.cli._fetch.copernicusmarine.open_dataset", fake_open_dataset
    )
    yield


@pytest.fixture
def expedition(tmpdir):
    out_path = tmpdir.join(EXPEDITION)

    with open(out_path, "w") as file:
        file.write(get_example_expedition())

    expedition = Expedition.from_yaml(out_path)

    return expedition


@pytest.mark.usefixtures("copernicus_no_download")
def test_fetch(expedition, tmpdir):
    """Test the fetch command, but mock the download and dataset metadata interrogation."""
    _fetch(Path(tmpdir), "test", "test")


def test_create_hash():
    assert len(create_hash("correct-length")) == 8
    assert create_hash("same") == create_hash("same")
    assert create_hash("unique1") != create_hash("unique2")


def test_hash_filename_roundtrip():
    hash_ = create_hash("test")
    assert filename_to_hash(hash_to_filename(hash_)) == hash_


def test_hash_model():
    class TestModel(BaseModel):
        a: int
        b: str

    hash_model(TestModel(a=0, b="b"))


def test_complete_download(tmp_path):
    # Setup
    DownloadMetadata(download_complete=False).to_yaml(tmp_path / DOWNLOAD_METADATA)

    complete_download(tmp_path)

    assert_complete_download(tmp_path)


def test_assert_complete_download_complete(tmp_path):
    # Setup
    DownloadMetadata(download_complete=True).to_yaml(tmp_path / DOWNLOAD_METADATA)

    assert_complete_download(tmp_path)


def test_assert_complete_download_incomplete(tmp_path):
    # Setup
    DownloadMetadata(download_complete=False).to_yaml(tmp_path / DOWNLOAD_METADATA)

    with pytest.raises(IncompleteDownloadError):
        assert_complete_download(tmp_path)


def test_assert_complete_download_missing(tmp_path):
    with pytest.raises(IncompleteDownloadError):
        assert_complete_download(tmp_path)


@pytest.fixture
def existing_data_folder(tmp_path, monkeypatch):
    # Setup
    folders = [
        "YYYYMMDD_HHMMSS_hash",
        "YYYYMMDD_HHMMSS_hash2",
        "some-invalid-data-folder",
        "YYYYMMDD_HHMMSS_hash3",
    ]
    data_folder = tmp_path
    monkeypatch.setattr(
        "virtualship.cli._fetch.assert_complete_download", lambda x: None
    )
    for f in folders:
        (data_folder / f).mkdir()
    yield data_folder


def test_get_existing_download(existing_data_folder):
    assert isinstance(get_existing_download(existing_data_folder, "hash"), Path)
    assert get_existing_download(existing_data_folder, "missing-hash") is None
