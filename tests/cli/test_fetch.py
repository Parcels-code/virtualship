from pathlib import Path

import numpy as np
import pytest
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
from virtualship.models import Schedule, ShipConfig
from virtualship.utils import get_example_config, get_example_schedule


@pytest.fixture
def copernicus_no_download(monkeypatch):
    """Mock the download and open_dataset functions."""

    # mock for copernicusmarine.subset
    def fake_download(output_filename, output_directory, **_):
        Path(output_directory).joinpath(output_filename).touch()

    # mock for copernicusmarine.open_dataset
    class DummyTime:
        def __getitem__(self, idx):
            return self

        @property
        def values(self):
            return np.datetime64("2023-02-01")

    class DummyDS(dict):
        def __getitem__(self, key):
            if key == "time":
                return DummyTime()
            raise KeyError(key)

    def fake_open_dataset(*args, **kwargs):
        return DummyDS()

    monkeypatch.setattr("virtualship.cli._fetch.copernicusmarine.subset", fake_download)
    monkeypatch.setattr(
        "virtualship.cli._fetch.copernicusmarine.open_dataset", fake_open_dataset
    )
    yield


@pytest.fixture
def schedule(tmpdir):
    out_path = tmpdir.join("schedule.yaml")

    with open(out_path, "w") as file:
        file.write(get_example_schedule())

    schedule = Schedule.from_yaml(out_path)

    return schedule


@pytest.fixture
def ship_config(tmpdir):
    out_path = tmpdir.join("ship_config.yaml")

    with open(out_path, "w") as file:
        file.write(get_example_config())

    ship_config = ShipConfig.from_yaml(out_path)

    return ship_config


@pytest.mark.usefixtures("copernicus_no_download")
def test_fetch(schedule, ship_config, tmpdir):
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


def test_select_product_id():
    ...
    # TODO


def test_start_end_in_product_timerange():
    ...
    # TODO


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
