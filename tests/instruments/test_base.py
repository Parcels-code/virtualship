from dataclasses import dataclass
from typing import ClassVar
from unittest.mock import MagicMock, patch

import numpy as np
import parcels
import pyarrow.parquet as pq
import pytest
import xarray as xr

from virtualship.instruments.base import (
    FetchSpec,
    Instrument,
    UnderwayCoordinates,
    UnderwayInstrument,
)
from virtualship.instruments.sensors import SensorType
from virtualship.instruments.types import InstrumentType
from virtualship.models.expedition import SensorConfig
from virtualship.utils import get_instrument_class

# =============================================================================
# Fixtures
# =============================================================================


@pytest.fixture()
def fieldset():
    """Minimal Parcels FieldSet containing a temperature field."""
    T = np.zeros((2, 1, 1))
    T[0, 0, 0], T[1, 0, 0] = 15.0, 16.0

    t1 = np.datetime64("2024-01-01T00:00:00")
    t2 = np.datetime64("2024-01-02T00:00:00")

    ds_fields = xr.Dataset(
        data_vars={"temperature": (["time", "lat", "lon"], T, {"units": "degC"})},
        coords={
            "time": ("time", [t1, t2], {"axis": "T"}),
            "lat": ("lat", [0.0], {"units": "degrees_north"}),
            "lon": ("lon", [0.0], {"units": "degrees_east"}),
        },
    )

    fields = {"T": ds_fields["temperature"]}
    ds_fset = parcels.convert.copernicusmarine_to_sgrid(fields=fields)
    return parcels.FieldSet.from_sgrid_conventions(ds_fset)


@pytest.fixture()
def pset(fieldset):
    """Minimal ParticleSet initialized with a custom Particle class and the fieldset fixture."""
    SampleParticle = parcels.Particle.add_variable(parcels.Variable("temperature"))
    t1 = np.datetime64("2024-01-01T00:00:00")

    return parcels.ParticleSet(
        fieldset=fieldset, pclass=SampleParticle, t=t1, y=[0.0], x=[0.0]
    )


# =============================================================================
# Instrument base class testing
# =============================================================================


def test_FetchSpec():
    fetch_spec = FetchSpec()

    # test that default values are set
    assert fetch_spec.latlon_buffer is not None
    assert fetch_spec.time_buffer is not None

    # test setting values (in new instance) and that original is unchanged in memory
    fetch_spec2 = FetchSpec(latlon_buffer=0.5, time_buffer=1.0)
    assert fetch_spec2.latlon_buffer == 0.5
    assert fetch_spec2.time_buffer == 1.0

    assert fetch_spec.latlon_buffer != fetch_spec2.latlon_buffer


def test_all_instruments_have_instrument_class():
    for instrument in InstrumentType:
        instrument_class = get_instrument_class(instrument)
        assert instrument_class is not None, f"No instrument_class for {instrument}"


class DummyInstrument(Instrument):
    """Minimal concrete Instrument for testing."""

    sensor_kernels = {}  # noqa

    def simulate(self, data_dir, measurements, out_path):
        """Dummy simulate implementation for test."""
        self.simulate_called = True

    @property
    def instrument_type(self) -> InstrumentType:
        """Return a valid InstrumentType for the test."""
        return InstrumentType.CTD


def test_load_input_data():
    """Test Instrument.load_input_data with mocks."""
    mock_waypoint = MagicMock()
    mock_waypoint.location.latitude = 1.0
    mock_waypoint.location.longitude = 2.0

    dummy = DummyInstrument(
        expedition=MagicMock(schedule=MagicMock(waypoints=[mock_waypoint])),
        variables={"A": "a"},
        add_bathymetry=False,
        allow_time_extrapolation=False,
        verbose_progress=False,
        from_data=None,
    )

    mock_fieldset = MagicMock()
    mock_fieldset.to_windowed_arrays.return_value = mock_fieldset

    with (
        patch(
            "virtualship.instruments.base._select_product_id",
            return_value="dummy_product_id",
        ),
        patch("copernicusmarine.open_dataset"),
        patch.object(dummy, "_via_tmp_ds", side_effect=lambda ds: ds),
        patch("parcels.convert.copernicusmarine_to_sgrid"),
        patch(
            "parcels.FieldSet.from_sgrid_conventions", return_value=mock_fieldset
        ) as mock_from_sgrid,
    ):
        fieldset = dummy.load_input_data()

    mock_from_sgrid.assert_called_once()
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


def test_fetch_spec_applied_to_instrument():
    """FetchSpec values are correctly stored on the instrument."""
    mock_waypoint = MagicMock()
    mock_waypoint.location.latitude = 1.0
    mock_waypoint.location.longitude = 2.0
    mock_schedule = MagicMock()
    mock_schedule.waypoints = [mock_waypoint]
    fetch_spec = FetchSpec(latlon_buffer=5.0, depth_min=-10.0)
    dummy = DummyInstrument(
        expedition=MagicMock(schedule=mock_schedule),
        variables={"A": "a"},
        add_bathymetry=False,
        allow_time_extrapolation=False,
        verbose_progress=False,
        fetch_spec=fetch_spec,
        from_data=None,
    )
    assert dummy.fetch_spec.latlon_buffer == 5.0
    assert dummy.fetch_spec.depth_min == -10.0
    # unset values use dataclass defaults
    assert dummy.fetch_spec.time_buffer == 0.0
    assert dummy.fetch_spec.depth_max is None


def test_via_tmp_ds_roundtrip():
    """_via_tmp_ds writes to a tmp file and re-opens it."""
    ds = xr.Dataset(
        {"temperature": (["x", "y"], [[1.0, 2.0], [3.0, 4.0]])},
        coords={"x": [0, 1], "y": [10, 20]},
    )
    result = Instrument._via_tmp_ds(ds)

    assert isinstance(result, xr.Dataset)
    assert "temperature" in result
    assert (
        result is not ds
    )  # result is new object loaded from tmp file, not the original


def test_generate_fieldset_combines_fields():
    mock_waypoint = MagicMock()
    mock_waypoint.location.latitude = 1.0
    mock_waypoint.location.longitude = 2.0

    dummy = DummyInstrument(
        expedition=MagicMock(schedule=MagicMock(waypoints=[mock_waypoint])),
        variables={"A": "a", "B": "b"},
        add_bathymetry=False,
        allow_time_extrapolation=False,
        verbose_progress=False,
        from_data=None,
    )

    fs_A = MagicMock()
    fs_B = MagicMock()

    fs_A.to_windowed_arrays.return_value = fs_A
    fs_B.to_windowed_arrays.return_value = fs_B

    with (
        patch.object(dummy, "_get_copernicus_ds"),
        patch.object(dummy, "_via_tmp_ds"),
        patch("parcels.convert.copernicusmarine_to_sgrid"),
        patch("parcels.FieldSet.from_sgrid_conventions", side_effect=[fs_A, fs_B]),
    ):
        dummy._generate_fieldset()

    fs_A.__add__.assert_called_once_with(fs_B)


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


def test_instrument_subclass_without_sensor_kernels_error():
    """Defining a concrete Instrument subclass without sensor_kernels raises TypeError."""
    with pytest.raises(TypeError, match="sensor_kernels"):

        class ErrorInstrument(Instrument):
            def simulate(self, data_dir, measurements, out_path):
                pass


def test_instrument_samples_initial_conditions(fieldset, pset):
    """_sample_initial adds initial conditions to particles."""
    psetT_preinit = pset.temperature.copy()  # before sampling initial conditions

    sensor_config = SensorConfig(sensor_type=SensorType.TEMPERATURE, enabled=True)
    pset = Instrument._sample_initial(pset, fieldset, [sensor_config])

    psetT_postinit = pset.temperature  # once initialised

    assert not np.array_equal(psetT_preinit, psetT_postinit), (
        "Initial conditions were not added."
    )

    assert np.allclose(psetT_postinit, [15.0]), (
        "Initial conditions do not match expected values."
    )


# =============================================================================
# UnderwayInstrument intermediate class testing
# =============================================================================


@dataclass
class DummySensorConfig:
    """Mock sensor configuration."""

    sensor_type: SensorType
    enabled: bool = True


class ConcreteUnderwayInstrument(UnderwayInstrument):
    """Concrete subclass of UnderwayInstrument for testing."""

    sensor_kernels: ClassVar = {
        SensorType.TEMPERATURE: lambda fieldset, coords: np.array(
            [15.0, 16.0], dtype=np.float32
        ),
        SensorType.SALINITY: lambda fieldset, coords: np.array(
            [35.0, 35.1], dtype=np.float32
        ),
        SensorType.VELOCITY: lambda fieldset, coords: (
            np.array([0.5, 0.6], dtype=np.float32),  # U vector component
            np.array([-0.1, -0.2], dtype=np.float32),  # V vector component
        ),
    }

    def simulate(self, measurements, out_path) -> None:  # noqa
        pass


@pytest.fixture
def sample_underway_coords():
    """Fixture providing valid 1D UnderwayCoordinates."""
    return UnderwayCoordinates(
        times=np.array([0.0, 3600.0]),
        lons=np.array([-5.0, -5.1]),
        lats=np.array([50.0, 50.1]),
        depths=np.array([-2.0, -2.0]),
    )


@pytest.fixture
def dummy_underway_inst():
    """Bypass __init__ and requirements for expedition object etc. for testing."""
    return ConcreteUnderwayInstrument.__new__(ConcreteUnderwayInstrument)


def test_underway_coordinates_validation():
    """UnderwayCoordinates validates array lengths upon instantiation."""
    # valid coordinates work cleanly
    coords = UnderwayCoordinates(
        times=np.array([0.0, 1.0]),
        lons=np.array([10.0, 11.0]),
        lats=np.array([20.0, 21.0]),
        depths=np.array([-1.0, -1.0]),
    )
    assert len(coords.times) == 2

    # mismatched array lengths raise ValueError
    with pytest.raises(ValueError, match="Array length mismatch"):
        UnderwayCoordinates(
            times=np.array([0.0, 1.0]),
            lons=np.array([10.0]),  # length 1 vs 2
            lats=np.array([20.0, 21.0]),
            depths=np.array([-1.0, -1.0]),
        )


def test_sample_underway_filters_and_flattens(
    dummy_underway_inst, sample_underway_coords
):
    """_sample_underway evaluates active sensors and flattens multi-output tuple kernels."""
    configs = [
        DummySensorConfig(SensorType.VELOCITY, enabled=True),
        DummySensorConfig(SensorType.TEMPERATURE, enabled=True),
        DummySensorConfig(SensorType.SALINITY, enabled=True),
    ]

    sampled = dummy_underway_inst._sample_underway(
        config_sensors=configs,
        fieldset=None,
        coords=sample_underway_coords,
    )

    assert len(sampled) == 4  # total flattened arrays (u, v, temp, sal)
    np.testing.assert_array_equal(sampled[0], np.array([0.5, 0.6], dtype=np.float32))
    np.testing.assert_array_equal(sampled[1], np.array([-0.1, -0.2], dtype=np.float32))
    np.testing.assert_array_equal(sampled[2], np.array([15.0, 16.0], dtype=np.float32))
    np.testing.assert_array_equal(sampled[3], np.array([35.0, 35.1], dtype=np.float32))


def test_to_parquet_writes_valid_file(
    tmp_path, dummy_underway_inst, sample_underway_coords
):
    """_to_parquet writes a valid Parquet table with expected schema metadata and data values."""
    out_path = tmp_path / "output.parquet"
    dat_arrays = [
        np.array([15.0, 16.0], dtype=np.float32),
        np.array([35.0, 35.1], dtype=np.float32),
    ]
    var_names = ["temp", "sal"]
    origin = np.datetime64("2026-01-01T00:00:00")

    dummy_underway_inst._to_parquet(
        dat_arrays=dat_arrays,
        var_names=var_names,
        fieldset_time_origin=origin,
        out_path=out_path,
        coords=sample_underway_coords,
    )

    assert out_path.exists()

    # verify parquet table, metadata, and columns
    table = pq.read_table(out_path)
    schema = table.schema

    assert table.column_names == [
        "t",
        "z",
        "y",
        "x",
        "particle_id",
        "temp",
        "sal",
    ]
    assert schema.metadata[b"feature_type"] == b"trajectory"
    assert b"units" in schema.field("t").metadata

    np.testing.assert_array_equal(
        table["x"].to_numpy(), np.array(sample_underway_coords.lons, dtype=np.float32)
    )
    np.testing.assert_array_equal(table["temp"].to_numpy(), dat_arrays[0])


def _create_underway_parquet(
    out_path,
    var_names,
    dat_arrays=None,
    origin=np.datetime64("2026-01-01T00:00:00"),  # noqa
):
    """Helper to generate an UnderwayInstrument parquet output file."""
    coords = UnderwayCoordinates(
        times=np.array([0.0, 3600.0]),
        lons=np.array([-5.0, -5.1]),
        lats=np.array([50.0, 50.1]),
        depths=np.array([-2.0, -2.0]),
    )

    if dat_arrays is None:
        dat_arrays = [
            np.array([15.0, 16.0], dtype=np.float32),
            np.array([35.0, 35.1], dtype=np.float32),
        ]

    UnderwayInstrument._to_parquet(
        dat_arrays=dat_arrays,
        var_names=var_names,
        fieldset_time_origin=origin,
        out_path=out_path,
        coords=coords,
    )


def dummy_sample_temperature(particles, fieldset):
    particles.temperature = fieldset.T[
        particles.t, particles.z, particles.y, particles.x
    ]


def test_parquet_openable_by_parcels_read_particlefile(tmp_path):
    """Test that a parquet file written by _to_parquet can be read back by parcels.read_particlefile."""
    parquet_path = tmp_path / "test_particles.parquet"
    _create_underway_parquet(
        out_path=parquet_path,
        var_names=["temp", "sal"],
        dat_arrays=[
            np.array([15.0, 16.0], dtype=np.float32),
            np.array([35.0, 35.1], dtype=np.float32),
        ],
    )

    # read back and assert values
    results = parcels.read_particlefile(parquet_path)
    assert len(results) == 2
    assert np.isclose(results["temp"][0], 15.0)
    assert np.isclose(results["sal"][1], 35.1)


def test_underway_schema_matches_parcels(tmp_path, pset):
    """Verify that underway instrument parquet output base schema matches Parcels' ParticleFile."""
    parcels_path = tmp_path / "parcels_particles.parquet"
    parcels_output = parcels.ParticleFile(parcels_path, outputdt=3600.0)
    pset.execute(
        [dummy_sample_temperature],
        runtime=np.timedelta64(60, "m"),
        dt=np.timedelta64(60, "m"),
        output_file=parcels_output,
    )
    parcels_df = parcels.read_particlefile(parcels_path)

    # UnderwayInstrument output
    underway_path = tmp_path / "underway_particles.parquet"
    _create_underway_parquet(
        out_path=underway_path,
        var_names=["temperature"],
        dat_arrays=[np.array([15.0, 16.0], dtype=np.float32)],
        origin=np.datetime64("2024-01-01T00:00:00"),
    )
    underway_df = parcels.read_particlefile(underway_path)

    # assert schemas match
    assert parcels_df.schema == underway_df.schema
