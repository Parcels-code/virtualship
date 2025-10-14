import datetime
from unittest.mock import patch

import pytest

from virtualship.models.instruments import InputDataset
from virtualship.models.space_time_region import (
    SpaceTimeRegion,
    SpatialRange,
    TimeRange,
)


class DummyInputDataset(InputDataset):
    """A minimal InputDataset subclass for testing purposes."""

    def get_datasets_dict(self):
        """Return a dummy datasets dict for testing."""
        return {
            "dummy": {
                "dataset_id": "test_id",
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


def test_inputdataset_abstract_instantiation():
    # instantiation should not be allowed
    with pytest.raises(TypeError):
        InputDataset(
            name="test",
            latlon_buffer=0,
            datetime_buffer=0,
            min_depth=0,
            max_depth=10,
            data_dir=".",
            credentials={"username": "u", "password": "p"},
            space_time_region=None,
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


@patch("virtualship.models.instruments.copernicusmarine.subset")
def test_download_data_calls_subset(mock_subset, dummy_space_time_region):
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
