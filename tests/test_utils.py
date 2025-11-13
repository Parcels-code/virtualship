from pathlib import Path

import numpy as np
import pytest
import xarray as xr

import virtualship.utils
from parcels import FieldSet
from virtualship.models.expedition import Expedition
from virtualship.utils import (
    _find_nc_file_with_variable,
    _get_bathy_data,
    _select_product_id,
    _start_end_in_product_timerange,
    add_dummy_UV,
    get_example_expedition,
)


@pytest.fixture
def expedition(tmp_file):
    with open(tmp_file, "w") as file:
        file.write(get_example_expedition())
    return Expedition.from_yaml(tmp_file)


@pytest.fixture
def dummy_spatial_range():
    class DummySpatialRange:
        minimum_longitude = 0
        maximum_longitude = 1
        minimum_latitude = 0
        maximum_latitude = 1
        minimum_depth = 0
        maximum_depth = 4

    return DummySpatialRange()


@pytest.fixture
def dummy_time_range():
    class DummyTimeRange:
        start_time = "2020-01-01"
        end_time = "2020-01-02"

    return DummyTimeRange()


@pytest.fixture
def dummy_space_time_region(dummy_spatial_range, dummy_time_range):
    class DummySpaceTimeRegion:
        spatial_range = dummy_spatial_range
        time_range = dummy_time_range

    return DummySpaceTimeRegion()


@pytest.fixture
def dummy_instrument():
    class DummyInstrument:
        pass

    return DummyInstrument()


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
                        np.datetime64("1993-01-01"),
                        np.datetime64("2022-01-01"),
                    ],  # mock up rough renanalysis period
                )
            }
        )

    monkeypatch.setattr("virtualship.utils.copernicusmarine.subset", fake_download)
    monkeypatch.setattr(
        "virtualship.utils.copernicusmarine.open_dataset", fake_open_dataset
    )
    yield


def test_get_example_expedition():
    assert len(get_example_expedition()) > 0


def test_valid_example_expedition(tmp_path):
    path = tmp_path / "test.yaml"
    with open(path, "w") as file:
        file.write(get_example_expedition())

    Expedition.from_yaml(path)


def test_instrument_registry_updates(dummy_instrument):
    from virtualship import utils

    utils.register_instrument("DUMMY_TYPE")(dummy_instrument)

    assert utils.INSTRUMENT_CLASS_MAP["DUMMY_TYPE"] is dummy_instrument


def test_add_dummy_UV_adds_fields():
    fieldset = FieldSet.from_data({"T": 1}, {"lon": 0, "lat": 0}, mesh="spherical")
    fieldset.__dict__.pop("U", None)
    fieldset.__dict__.pop("V", None)

    # should not have U or V fields initially
    assert "U" not in fieldset.__dict__
    assert "V" not in fieldset.__dict__

    add_dummy_UV(fieldset)

    # now U and V should be present
    assert "U" in fieldset.__dict__
    assert "V" in fieldset.__dict__

    # should not raise error if U and V already present
    add_dummy_UV(fieldset)


@pytest.mark.usefixtures("copernicus_no_download")
def test_select_product_id(expedition):
    """Should return the physical reanalysis product id via the timings prescribed in the static schedule.yaml file."""
    result = _select_product_id(
        physical=True,
        schedule_start=expedition.schedule.space_time_region.time_range.start_time,
        schedule_end=expedition.schedule.space_time_region.time_range.end_time,
        username="test",
        password="test",
    )
    assert result == "cmems_mod_glo_phy_my_0.083deg_P1D-m"


@pytest.mark.usefixtures("copernicus_no_download")
def test_start_end_in_product_timerange(expedition):
    """Should return True for valid range ass determined by the static schedule.yaml file."""
    assert _start_end_in_product_timerange(
        selected_id="cmems_mod_glo_phy_my_0.083deg_P1D-m",
        schedule_start=expedition.schedule.space_time_region.time_range.start_time,
        schedule_end=expedition.schedule.space_time_region.time_range.end_time,
        username="test",
        password="test",
    )


def test_get_bathy_data_local(tmp_path, dummy_space_time_region):
    """Test that _get_bathy_data returns a FieldSet when given a local directory for --from-data."""
    # dummy .nc file with 'deptho' variable
    data = np.array([[1, 2], [3, 4]])
    ds = xr.Dataset(
        {
            "deptho": (("x", "y"), data),
        },
        coords={
            "longitude": (("x", "y"), np.array([[0, 1], [0, 1]])),
            "latitude": (("x", "y"), np.array([[0, 0], [1, 1]])),
        },
    )
    nc_path = tmp_path / "bathymetry/dummy.nc"
    nc_path.parent.mkdir(parents=True, exist_ok=True)
    ds.to_netcdf(nc_path)

    # should return a FieldSet
    fieldset = _get_bathy_data(dummy_space_time_region, from_data=tmp_path)
    assert isinstance(fieldset, FieldSet)
    assert hasattr(fieldset, "bathymetry")
    assert np.allclose(fieldset.bathymetry.data, data)


def test_get_bathy_data_copernicusmarine(monkeypatch, dummy_space_time_region):
    """Test that _get_bathy_data calls copernicusmarine by default."""

    def dummy_copernicusmarine(*args, **kwargs):
        raise RuntimeError("copernicusmarine called")

    monkeypatch.setattr(
        virtualship.utils.copernicusmarine, "open_dataset", dummy_copernicusmarine
    )

    try:
        _get_bathy_data(dummy_space_time_region)
    except RuntimeError as e:
        assert "copernicusmarine called" in str(e)


def test_find_nc_file_with_variable_substring(tmp_path):
    # dummy .nc file with variable 'uo_glor' (possible for CMS products to have similar suffixes...)
    data = np.array([[1, 2], [3, 4]])
    ds = xr.Dataset(
        {
            "uo_glor": (("x", "y"), data),
        },
        coords={
            "longitude": (("x", "y"), np.array([[0, 1], [0, 1]])),
            "latitude": (("x", "y"), np.array([[0, 0], [1, 1]])),
        },
    )
    nc_path = tmp_path / "test.nc"
    ds.to_netcdf(nc_path)

    # should find 'uo_glor' when searching for 'uo'
    result = _find_nc_file_with_variable(tmp_path, "uo")
    assert result is not None
    filename, found_var = result
    assert filename == "test.nc"
    assert found_var == "uo_glor"


# TODO: add test that pre-downloaded data is in correct directories - when have moved to be able to handle temporally separated .nc files!
