import datetime
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
    """Should return the physical reanalysis product id via the timings prescribed."""
    result = _select_product_id(
        physical=True,
        schedule_start=datetime.datetime(
            1995, 6, 1, 0, 0, 0
        ),  # known to be in reanalysis range
        schedule_end=datetime.datetime(1995, 6, 30, 0, 0, 0),
        username="test",
        password="test",
    )
    assert result == "cmems_mod_glo_phy_my_0.083deg_P1D-m"


@pytest.mark.usefixtures("copernicus_no_download")
def test_start_end_in_product_timerange(expedition):
    """Should return True for valid range as determined by the static schedule.yaml file."""
    assert _start_end_in_product_timerange(
        selected_id="cmems_mod_glo_phy_my_0.083deg_P1D-m",
        schedule_start=datetime.datetime(1995, 6, 1, 0, 0, 0),
        schedule_end=datetime.datetime(1995, 6, 30, 0, 0, 0),
        username="test",
        password="test",
    )


def test_get_bathy_data_local(tmp_path):
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
    fieldset = _get_bathy_data(
        min_lat=0.25, max_lat=0.75, min_lon=0.25, max_lon=0.75, from_data=tmp_path
    )
    assert isinstance(fieldset, FieldSet)
    assert hasattr(fieldset, "bathymetry")
    assert np.allclose(fieldset.bathymetry.data, data)


def test_get_bathy_data_copernicusmarine(monkeypatch):
    """Test that _get_bathy_data calls copernicusmarine by default."""

    def dummy_copernicusmarine(*args, **kwargs):
        raise RuntimeError("copernicusmarine called")

    monkeypatch.setattr(
        virtualship.utils.copernicusmarine, "open_dataset", dummy_copernicusmarine
    )

    try:
        _get_bathy_data(min_lat=0.25, max_lat=0.75, min_lon=0.25, max_lon=0.75)
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


def test_data_dir_and_filename_compliance():
    """
    Test compliance of data directory structure and filename patterns as sought by base.py methods relative to as is described in the docs.

    Test that:
        - Instrument._generate_fieldset and _get_bathy_data use the expected subdirectory names.
        - The expected filename date pattern (YYYY_MM_DD) is used in _find_files_in_timerange.


    ('phys', 'bgc', 'bathymetry') for local data loading, as required by documentation.

    To avoid drift between code implementation and what expectations are laid out in the docs.
    """
    base_path = Path(__file__).parent.parent / "src/virtualship/instruments/base.py"
    utils_path = Path(__file__).parent.parent / "src/virtualship/utils.py"

    base_code = base_path.read_text(encoding="utf-8")
    utils_code = utils_path.read_text(encoding="utf-8")

    # Check for phys and bgc in Instrument._generate_fieldset
    assert 'self.from_data.joinpath("phys")' in base_code, (
        "Expected 'phys' subdirectory not found in Instrument._generate_fieldset. This indicates a drift between docs and implementation."
    )
    assert 'self.from_data.joinpath("bgc")' in base_code, (
        "Expected 'bgc' subdirectory not found in Instrument._generate_fieldset. This indicates a drift between docs and implementation."
    )

    # Check for bathymetry in _get_bathy_data
    assert 'from_data.joinpath("bathymetry")' in utils_code, (
        "Expected 'bathymetry' subdirectory not found in _get_bathy_data. This indicates a drift between docs and implementation."
    )

    # Check for date_pattern in _find_files_in_timerange
    assert 'date_pattern=r"\\d{4}_\\d{2}_\\d{2}"' in utils_code, (
        "Expected date_pattern r'\\d{4}_\\d{2}_\\d{2}' not found in _find_files_in_timerange. This indicates a drift between docs and implementation."
    )

    # Check for P1D and P1M in t_resolution logic
    assert 'if all("P1D" in s for s in all_files):' in utils_code, (
        "Expected check for 'P1D' in all_files not found in _find_files_in_timerange. This indicates a drift between docs and implementation."
    )
    assert 'elif all("P1M" in s for s in all_files):' in utils_code, (
        "Expected check for 'P1M' in all_files not found in _find_files_in_timerange. This indicates a drift between docs and implementation."
    )


# TODO: test for calc_sail_time

# TODO: test for calc_stationkeeping_time
