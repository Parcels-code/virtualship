from __future__ import annotations

import abc
import collections
import inspect
import tempfile
from dataclasses import dataclass
from datetime import timedelta
from itertools import pairwise
from pathlib import Path
from typing import TYPE_CHECKING, ClassVar, Literal

import copernicusmarine
import numpy as np
import parcels
import pyarrow as pa
import pyarrow.parquet as pq
import xarray as xr
from yaspin import yaspin

from virtualship.errors import CopernicusCatalogueError
from virtualship.instruments.types import InstrumentType
from virtualship.utils import (
    COPERNICUSMARINE_PHYS_VARIABLES,
    INSTRUMENT_CLASS_MAP,
    _find_files_in_timerange,
    _find_nc_file_with_variable,
    _get_bathy_data,
    _get_waypoint_latlons,
    _select_product_id,
    ship_spinner,
)

if TYPE_CHECKING:
    from virtualship.instruments.sensors import SensorType
    from virtualship.models import Expedition


@dataclass
class FetchSpec:
    """Fetch constraints and parameters for dataset retrieval."""

    spatial: bool = True
    latlon_buffer: float = 0.25  # degrees
    time_buffer: float = 0.0  # days
    depth_min: float | None = None
    depth_max: float | None = None


class Instrument(abc.ABC):
    """Base class for instruments and their simulation."""

    # all instruments have sensor_kernels dict, mapping SensorType to sampling kernel
    sensor_kernels: ClassVar[dict[SensorType, collections.abc.Callable]]

    def __init_subclass__(cls, **kwargs: object) -> None:
        """Ensure non-abstract subclasses (i.e. final/concrete instrument classes) define sensor_kernels as a class attribute."""
        super().__init_subclass__(**kwargs)
        if inspect.isabstract(cls):
            return

        if "sensor_kernels" not in cls.__dict__:
            raise TypeError(
                f"Instrument subclass '{cls.__name__}' must define 'sensor_kernels' as a class attribute."
            )

    def __init__(
        self,
        expedition: Expedition,
        variables: dict,
        add_bathymetry: bool,
        allow_time_extrapolation: bool,
        verbose_progress: bool,
        from_data: Path | None,
        fetch_spec: FetchSpec | None = None,
    ):
        """Initialise instrument."""
        self.expedition = expedition
        self.from_data = from_data

        self.variables = collections.OrderedDict(variables)
        self.dimensions = {
            "lon": "longitude",
            "lat": "latitude",
            "time": "time",
            "depth": "depth",
        }  # same dimensions for all instruments
        self.add_bathymetry = add_bathymetry
        self.allow_time_extrapolation = allow_time_extrapolation
        self.verbose_progress = verbose_progress
        self.fetch_spec = fetch_spec or FetchSpec()

        wp_lats, wp_lons = _get_waypoint_latlons(expedition.schedule.waypoints)
        wp_times = [
            wp.time for wp in expedition.schedule.waypoints if wp.time is not None
        ]
        assert all(earlier <= later for earlier, later in pairwise(wp_times)), (
            "Waypoint times are not in ascending order"
        )
        self.wp_times = wp_times

        self.min_time, self.max_time = (
            wp_times[0],
            wp_times[-1] + timedelta(days=1),
        )  # avoid edge issues
        self.min_lat, self.max_lat = min(wp_lats), max(wp_lats)
        self.min_lon, self.max_lon = min(wp_lons), max(wp_lons)

    def load_input_data(self) -> parcels.FieldSet:
        """Load and return the input data as a FieldSet for the instrument."""
        try:
            fieldset = self._generate_fieldset()
        except Exception as e:
            raise CopernicusCatalogueError(
                f"Failed to load input data directly from Copernicus Marine (or local data) for instrument '{self.__class__.__name__}'. Original error: {e}"
            ) from e

        # interpolation methods
        for var in (v for v in self.variables if v not in ("U", "V")):
            getattr(
                fieldset, var
            ).interp_method = parcels.interpolators.XLinearInvdistLandTracer()

        # bathymetry data
        if self.add_bathymetry:
            bathymetry_field = _get_bathy_data(from_data=self.from_data).bathymetry
            fieldset.add_field(bathymetry_field)

        return fieldset

    @abc.abstractmethod
    def simulate(
        self,
        data_dir: Path,
        measurements: list,
        out_path: str | Path,
    ) -> None:
        """Simulate instrument measurements."""

    def execute(self, measurements: list, out_path: str | Path) -> None:
        """Run instrument simulation."""
        TMP = False  # TODO: just for dev; remove before merging
        instrument_name = self.__class__.__name__.split("Instrument")[0]

        if not self.verbose_progress:
            if TMP:
                with yaspin(
                    text=f"Simulating {instrument_name} measurements... ",
                    side="right",
                    spinner=ship_spinner,
                ) as spinner:
                    self.simulate(measurements, out_path)
                    spinner.ok("✅\n")
            else:
                self.simulate(measurements, out_path)
        else:
            print(f"Simulating {instrument_name} measurements... ")
            self.simulate(measurements, out_path)
            print("\n")

    def _get_copernicus_ds(
        self,
        time_buffer: float | None,
        physical: bool,
        var: str,
    ) -> xr.Dataset:
        """Get Copernicus Marine dataset for direct ingestion."""
        product_id = _select_product_id(
            physical=physical,
            schedule_start=self.min_time,
            schedule_end=self.max_time,
            variable=var if not physical else None,
        )

        latlon_buffer = self.fetch_spec.latlon_buffer
        depth_min = self.fetch_spec.depth_min
        depth_max = self.fetch_spec.depth_max
        spatial_constraint = self.fetch_spec.spatial

        min_lon_bound = self.min_lon - latlon_buffer if spatial_constraint else None
        max_lon_bound = self.max_lon + latlon_buffer if spatial_constraint else None
        min_lat_bound = self.min_lat - latlon_buffer if spatial_constraint else None
        max_lat_bound = self.max_lat + latlon_buffer if spatial_constraint else None

        return copernicusmarine.open_dataset(
            dataset_id=product_id,
            minimum_longitude=min_lon_bound,
            maximum_longitude=max_lon_bound,
            minimum_latitude=min_lat_bound,
            maximum_latitude=max_lat_bound,
            variables=[var],
            start_datetime=self.min_time,
            end_datetime=self.max_time + timedelta(days=time_buffer),
            minimum_depth=depth_min,
            maximum_depth=depth_max,
            coordinates_selection_method="outside",
            vertical_axis="elevation",
        )

    def _generate_fieldset(self) -> parcels.FieldSet:
        """
        Create and combine FieldSets for each variable, supporting both local and Copernicus Marine data sources.

        N.B. Per variable avoids issues when using copernicusmarine and creating directly one FieldSet of ds's sourced from different Copernicus Marine product IDs (which can also have different temporal resolutions), which is often the case for BGC variables.

        Includes an intermediate step of writing to tmp files, as per https://github.com/Parcels-code/parcels-benchmarks/pull/49
        TODO: the need for this step may be removed as Parcels x copernicusmarine integration improves, tracked in https://github.com/Parcels-code/Parcels/issues/2756 and xref'd in VirtualShip #357 (https://github.com/Parcels-code/virtualship/issues/357)
        """
        fieldsets_list = []
        keys = list(self.variables.keys())

        time_buffer = self.fetch_spec.time_buffer

        for key in keys:
            var = self.variables[key]
            physical = var in COPERNICUSMARINE_PHYS_VARIABLES

            if self.from_data is not None:  # load from local data
                data_dir = self.from_data.joinpath("phys" if physical else "bgc")

                files = _find_files_in_timerange(
                    data_dir,
                    self.min_time,
                    self.max_time + timedelta(days=time_buffer),
                )

                _, field_var_name = _find_nc_file_with_variable(
                    data_dir, var
                )  # get full variable name from one of the files; var may only appear as substring in variable name in file

                ds = xr.open_mfdataset([data_dir.joinpath(f) for f in files])

                # TODO: for the local data it's useful to sel the relevant depth layer(s), in case the user's data is full depth

            else:  # stream via Copernicus Marine Service
                ds = self._get_copernicus_ds(
                    time_buffer,
                    physical=physical,
                    var=var,
                )
                field_var_name = var

            # TODO: to be removed when Parcels #2746 is merged (i.e. https://github.com/Parcels-code/Parcels/pull/2746)
            ds = ds.fillna(0)

            fields = {key: ds[field_var_name]}
            ds_fset = parcels.convert.copernicusmarine_to_sgrid(fields=fields)
            ds_fset = self._via_tmp_ds(ds_fset)

            fs = parcels.FieldSet.from_sgrid_conventions(ds_fset)

            # non-underway instruments to windowed arrays, just in case any ds is Dask backed
            # underway instruments should not to converted to windowed arrays, as they use one direct fieldset.eval() call which could cause a big memory usage if the fieldset is windowed
            if not self.instrument_type.is_underway:
                fs = fs.to_windowed_arrays()

            fieldsets_list.append(fs)

        base_fieldset = fieldsets_list[0]
        for fs, key in zip(fieldsets_list[1:], keys[1:], strict=False):
            base_fieldset.add_field(getattr(fs, key))

        # some instruments use AdvectionRKn kernels which require a combined UV vector field
        # fieldsets are created per variable and thus are not seen by from_sgrid_conventions at the same time, therefore build combined VectorField here in FieldSet
        if "U" in keys and "V" in keys:
            uv = parcels.VectorField(
                "UV",
                base_fieldset.U,
                base_fieldset.V,
                interp_method=parcels.interpolators.XLinear_Velocity(),
            )
            base_fieldset.add_field(uv)

        return base_fieldset

    @staticmethod
    def _via_tmp_ds(ds) -> xr.Dataset:
        """Create and re-load a temporary local dataset."""
        tmpdir = tempfile.TemporaryDirectory()
        tmp_fpath = Path(tmpdir.name).joinpath("tmp.nc")
        ds.to_netcdf(tmp_fpath)
        del ds
        return xr.open_dataset(tmp_fpath)

    @property
    def instrument_type(self) -> InstrumentType:
        """Return the InstrumentType for this instrument instance."""
        return next(k for k, v in INSTRUMENT_CLASS_MAP.items() if type(self) is v)


@dataclass(frozen=True)
class UnderwayCoordinates:
    """1D sampling location arrays for underway instruments."""

    times: np.ndarray  # seconds since origin
    lons: np.ndarray
    lats: np.ndarray
    depths: np.ndarray

    def __post_init__(self):
        """Validate that all arrays are 1D and have the same length."""
        shapes = {
            "times": self.times.shape,
            "lons": self.lons.shape,
            "lats": self.lats.shape,
            "depths": self.depths.shape,
        }

        for name, shape in shapes.items():
            if len(shape) != 1:
                raise ValueError(f"Array '{name}' must be 1D, but got shape {shape}.")

        n = len(self.times)
        if not (len(self.lons) == len(self.lats) == len(self.depths) == n):
            raise ValueError(
                f"Array length mismatch in UnderwayCoordinates: "
                f"times={len(self.times)}, lons={len(self.lons)}, "
                f"lats={len(self.lats)}, depths={len(self.depths)}"
            )


class UnderwayInstrument(Instrument):
    """Intermediate base class for underway instruments, which perform variable sampling without ParticleSets."""

    def _sample_underway(
        self,
        config_sensors: list,
        fieldset: parcels.FieldSet,
        coords: UnderwayCoordinates,
    ):
        """Perform variable sampling for underway instruments and their active sensors."""
        sampling_kernels = [
            self.sensor_kernels[sc.sensor_type]
            for sc in config_sensors
            if sc.enabled and sc.sensor_type in self.sensor_kernels
        ]  # active sensors only

        sampled = [
            kernel(fieldset, coords) for kernel in sampling_kernels
        ]  # perform sampling

        # ensure that sampled is a flat list of arrays, even if some kernels return tuples/lists of arrays
        # e.g. ADCP kernel returns (u, v) tuple of arrays, whilst UnderwaterST returns single array of temperature/salinity
        sampled_flat = [
            arr
            for item in sampled
            for arr in (item if isinstance(item, (tuple, list)) else (item,))
        ]

        return sampled_flat

    @staticmethod
    def _to_parquet(
        dat_arrays: list[np.ndarray],
        var_names: list[str],
        fieldset_time_origin: np.datetime64,
        out_path: Path | str,
        coords: UnderwayCoordinates,
        compression: Literal["zstd", "gzip", "snappy", "brotli", None] = "zstd",
    ) -> None:
        """
        Write underway instrument data to a Parquet file mirroring the Parcels v4 ParticleFile schema.

        Designed so that output files can be re-read back in with Parcels.read_particlefile for consistent downstream workflows with non-underway instruments.
        """
        assert len(dat_arrays) == len(var_names), (
            "dat_arrays and var_names must have the same length"
        )

        n = len(coords.times)

        origin_str = str(fieldset_time_origin).replace("T", " ")
        t_metadata = {"units": f"seconds since {origin_str}", "calendar": "standard"}

        # base schema mirroring Parcels ParticleFile schema, not yet with sampled variables
        base_schema = pa.schema(
            [
                pa.field("t", pa.float64(), metadata=t_metadata),
                pa.field("z", pa.float32()),
                pa.field("y", pa.float32()),
                pa.field("x", pa.float32()),
                pa.field("particle_id", pa.int64()),
            ],
            metadata={
                "feature_type": "trajectory",
                "Conventions": "CF-1.6/CF-1.7",
                "ncei_template_version": "NCEI_NetCDF_Trajectory_Template_v2.0",
                "parcels_version": parcels.__version__,
                "parcels_grid_mesh": "spherical",
            },
        )

        for var in var_names:
            base_schema = base_schema.append(
                pa.field(var, pa.float32())
            )  # add sampled variable to schema

        out_path = Path(out_path)
        if out_path.suffix != ".parquet":
            raise ValueError(
                f"out_path must end in '.parquet', got {out_path.suffix!r}"
            )

        # build table with all data, including sampled variables
        table = pa.table(
            {
                "t": pa.array(coords.times.astype(np.float64)),
                "z": pa.array(coords.depths.astype(np.float32))
                if coords.depths is not None
                else pa.array(np.full(n, np.nan, dtype=np.float32)),
                "y": pa.array(coords.lats.astype(np.float32)),
                "x": pa.array(coords.lons.astype(np.float32)),
                "particle_id": pa.array(
                    np.zeros(n, dtype=np.int64)
                ),  # ship is a single 'particle' (here represented by a constant particle_id of 0)
                "dt": pa.array(np.full(n, np.nan, dtype=np.float64)),
                "state": pa.array(np.zeros(n, dtype=np.int32)),
                **{
                    var: pa.array(dat.astype(np.float32))
                    for var, dat in zip(var_names, dat_arrays, strict=True)
                },
            },
            schema=base_schema,
        )

        pq.write_table(table, out_path, compression=compression)
