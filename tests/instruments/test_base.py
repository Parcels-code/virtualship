import datetime
from pathlib import Path
from unittest.mock import MagicMock, patch

import numpy as np
import pytest
import xarray as xr

from virtualship.instruments.base import InputDataset, Instrument
from virtualship.instruments.types import InstrumentType
from virtualship.models.space_time_region import (
    SpaceTimeRegion,
    SpatialRange,
    TimeRange,
)
from virtualship.utils import get_input_dataset_class

# test dataclass, particle class, kernels, etc. are defined for each instrument


def test_all_instruments_have_input_class():
    for instrument in InstrumentType:
        input_class = get_input_dataset_class(instrument)
        assert input_class is not None, f"No input_class for {instrument}"


# test InputDataset class


class DummyInputDataset(InputDataset):
    """A minimal InputDataset subclass for testing purposes."""

    def get_datasets_dict(self):
        """Return a dummy datasets dict for testing."""
        return {
            "dummy": {
                "physical": True,
                "variables": ["var1"],
                "output_filename": "dummy.nc",
            }
        }


@pytest.fixture
def dummy_space_time_region():
    spatial_range = SpatialRange(
        minimum_longitude=0,
        maximum_longitude=1,
        minimum_latitude=0,
        maximum_latitude=1,
        minimum_depth=0,
        maximum_depth=10,
    )
    base_time = datetime.datetime.strptime("1950-01-01", "%Y-%m-%d")
    time_range = TimeRange(
        start_time=base_time,
        end_time=base_time + datetime.timedelta(hours=1),
    )
    return SpaceTimeRegion(
        spatial_range=spatial_range,
        time_range=time_range,
    )


def test_dummyinputdataset_initialization(dummy_space_time_region):
    ds = DummyInputDataset(
        name="test",
        latlon_buffer=0.5,
        datetime_buffer=1,
        min_depth=0,
        max_depth=10,
        data_dir=".",
        credentials={"username": "u", "password": "p"},
        space_time_region=dummy_space_time_region,
    )
    assert ds.name == "test"
    assert ds.latlon_buffer == 0.5
    assert ds.datetime_buffer == 1
    assert ds.min_depth == 0
    assert ds.max_depth == 10
    assert ds.data_dir == "."
    assert ds.credentials["username"] == "u"


@patch("virtualship.instruments.base.copernicusmarine.open_dataset")
@patch("virtualship.instruments.base.copernicusmarine.subset")
def test_download_data_calls_subset(
    mock_subset, mock_open_dataset, dummy_space_time_region
):
    """Test that download_data calls the subset function correctly, will also test Copernicus Marine product id search logic."""
    mock_open_dataset.return_value = xr.Dataset(
        {
            "time": (
                "time",
                [
                    np.datetime64("1993-01-01T00:00:00"),
                    np.datetime64("2023-01-01T01:00:00"),
                ],
            )
        }
    )
    ds = DummyInputDataset(
        name="test",
        latlon_buffer=0.5,
        datetime_buffer=1,
        min_depth=0,
        max_depth=10,
        data_dir=".",
        credentials={"username": "u", "password": "p"},
        space_time_region=dummy_space_time_region,
    )
    ds.download_data()
    assert mock_subset.called


# test Instrument class


class DummyInstrument(Instrument):
    """Minimal concrete Instrument for testing."""

    def simulate(self, data_dir, measurements, out_path):
        """Dummy simulate implementation for test."""
        self.simulate_called = True


@patch("virtualship.instruments.base.FieldSet")
@patch("virtualship.instruments.base.get_existing_download")
@patch("virtualship.instruments.base.get_space_time_region_hash")
def test_load_input_data_calls(mock_hash, mock_get_download, mock_FieldSet):
    """Test Instrument.load_input_data with mocks."""
    mock_hash.return_value = "hash"
    mock_get_download.return_value = Path("/tmp/data")
    mock_fieldset = MagicMock()
    mock_FieldSet.from_netcdf.return_value = mock_fieldset
    mock_fieldset.gridset.grids = [MagicMock(negate_depth=MagicMock())]
    mock_fieldset.__getitem__.side_effect = lambda k: MagicMock()
    dummy = DummyInstrument(
        name="test",
        expedition=MagicMock(schedule=MagicMock(space_time_region=MagicMock())),
        directory="/tmp",
        filenames={"A": "a.nc"},
        variables={"A": "a"},
        add_bathymetry=False,
        allow_time_extrapolation=False,
        verbose_progress=False,
    )
    fieldset = dummy.load_input_data()
    assert mock_FieldSet.from_netcdf.called
    assert fieldset == mock_fieldset
