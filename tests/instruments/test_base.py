from unittest.mock import MagicMock, patch

from virtualship.instruments.base import Instrument
from virtualship.instruments.types import InstrumentType
from virtualship.utils import get_instrument_class


def test_all_instruments_have_instrument_class():
    for instrument in InstrumentType:
        instrument_class = get_instrument_class(instrument)
        assert instrument_class is not None, f"No instrument_class for {instrument}"


class DummyInstrument(Instrument):
    """Minimal concrete Instrument for testing."""

    def simulate(self, data_dir, measurements, out_path):
        """Dummy simulate implementation for test."""
        self.simulate_called = True


@patch("virtualship.instruments.base.FieldSet")
@patch(
    "virtualship.instruments.base._select_product_id", return_value="dummy_product_id"
)
@patch("virtualship.instruments.base.copernicusmarine")
def test_load_input_data(mock_copernicusmarine, mock_select_product_id, mock_FieldSet):
    """Test Instrument.load_input_data with mocks."""
    mock_fieldset = MagicMock()
    mock_FieldSet.from_netcdf.return_value = mock_fieldset
    mock_FieldSet.from_xarray_dataset.return_value = mock_fieldset
    mock_fieldset.gridset.grids = [MagicMock(negate_depth=MagicMock())]
    mock_fieldset.__getitem__.side_effect = lambda k: MagicMock()
    mock_copernicusmarine.open_dataset.return_value = MagicMock()
    # Create a mock waypoint with latitude and longitude
    mock_waypoint = MagicMock()
    mock_waypoint.location.latitude = 1.0
    mock_waypoint.location.longitude = 2.0
    mock_schedule = MagicMock()
    mock_schedule.waypoints = [mock_waypoint]
    dummy = DummyInstrument(
        expedition=MagicMock(schedule=mock_schedule),
        variables={"A": "a"},
        add_bathymetry=False,
        allow_time_extrapolation=False,
        verbose_progress=False,
        from_data=None,
    )
    fieldset = dummy.load_input_data()
    assert mock_FieldSet.from_xarray_dataset.called
    assert fieldset == mock_fieldset
    assert fieldset == mock_fieldset


def test_execute_calls_simulate(monkeypatch):
    mock_waypoint = MagicMock()
    mock_waypoint.location.latitude = 1.0
    mock_waypoint.location.longitude = 2.0
    mock_schedule = MagicMock()
    mock_schedule.waypoints = [mock_waypoint]
    dummy = DummyInstrument(
        expedition=MagicMock(schedule=mock_schedule),
        variables={"A": "a"},
        add_bathymetry=False,
        allow_time_extrapolation=False,
        verbose_progress=True,
        from_data=None,
    )
    dummy.simulate = MagicMock()
    dummy.execute([1, 2, 3], "/tmp/out")
    dummy.simulate.assert_called_once()


def test_get_spec_value_buffer_and_limit():
    mock_waypoint = MagicMock()
    mock_waypoint.location.latitude = 1.0
    mock_waypoint.location.longitude = 2.0
    mock_schedule = MagicMock()
    mock_schedule.waypoints = [mock_waypoint]
    dummy = DummyInstrument(
        expedition=MagicMock(schedule=mock_schedule),
        variables={"A": "a"},
        add_bathymetry=False,
        allow_time_extrapolation=False,
        verbose_progress=False,
        spacetime_buffer_size={"latlon": 5.0},
        limit_spec={"depth_min": 10.0},
        from_data=None,
    )
    assert dummy._get_spec_value("buffer", "latlon", 0.0) == 5.0
    assert dummy._get_spec_value("limit", "depth_min", None) == 10.0
    assert dummy._get_spec_value("buffer", "missing", 42) == 42


def test_generate_fieldset_combines_fields(monkeypatch):
    mock_waypoint = MagicMock()
    mock_waypoint.location.latitude = 1.0
    mock_waypoint.location.longitude = 2.0
    mock_schedule = MagicMock()
    mock_schedule.waypoints = [mock_waypoint]
    dummy = DummyInstrument(
        expedition=MagicMock(schedule=mock_schedule),
        variables={"A": "a", "B": "b"},
        add_bathymetry=False,
        allow_time_extrapolation=False,
        verbose_progress=False,
        from_data=None,
    )
    dummy.from_data = None

    monkeypatch.setattr(
        dummy, "_get_copernicus_ds", lambda *args, **kwargs: MagicMock()
    )

    fs_A = MagicMock()
    fs_B = MagicMock()
    fs_B.B = MagicMock()
    monkeypatch.setattr(
        "virtualship.instruments.base.FieldSet.from_xarray_dataset",
        lambda ds, varmap, dims, mesh=None: fs_A if "A" in varmap else fs_B,
    )
    monkeypatch.setattr(fs_A, "add_field", MagicMock())
    dummy._generate_fieldset()
    fs_A.add_field.assert_called_once_with(fs_B.B)


def test_load_input_data_error(monkeypatch):
    mock_waypoint = MagicMock()
    mock_waypoint.location.latitude = 1.0
    mock_waypoint.location.longitude = 2.0
    mock_schedule = MagicMock()
    mock_schedule.waypoints = [mock_waypoint]
    dummy = DummyInstrument(
        expedition=MagicMock(schedule=mock_schedule),
        variables={"A": "a"},
        add_bathymetry=False,
        allow_time_extrapolation=False,
        verbose_progress=False,
        from_data=None,
    )
    monkeypatch.setattr(
        dummy, "_generate_fieldset", lambda: (_ for _ in ()).throw(Exception("fail"))
    )
    import virtualship.errors

    try:
        dummy.load_input_data()
    except virtualship.errors.CopernicusCatalogueError as e:
        assert "Failed to load input data" in str(e)
