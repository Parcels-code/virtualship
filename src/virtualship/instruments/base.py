import abc
from collections import OrderedDict
from datetime import timedelta
from pathlib import Path
from typing import TYPE_CHECKING

import copernicusmarine
import xarray as xr
from yaspin import yaspin

from parcels import FieldSet
from virtualship.errors import CopernicusCatalogueError
from virtualship.utils import (
    COPERNICUSMARINE_PHYS_VARIABLES,
    _find_nc_file_with_variable,
    _get_bathy_data,
    _select_product_id,
    ship_spinner,
)

if TYPE_CHECKING:
    from virtualship.models import Expedition


# TODO: from-data should default to None and only be overwritten if specified in `virtualship run` ...

# TODO: update CMS credentials automation workflow so not all using the same credentials if running in a Jupyter Collaborative Session...!


class Instrument(abc.ABC):
    """Base class for instruments and their simulation."""

    def __init__(
        self,
        name: str,
        expedition: "Expedition",
        directory: Path | str,
        filenames: dict,
        variables: dict,
        add_bathymetry: bool,
        allow_time_extrapolation: bool,
        verbose_progress: bool,
        from_data: Path | None,
        buffer_spec: dict | None = None,
        limit_spec: dict | None = None,
    ):
        """Initialise instrument."""
        self.name = name
        self.expedition = expedition
        self.directory = directory
        self.filenames = filenames
        self.from_data = from_data

        self.variables = OrderedDict(variables)
        self.dimensions = {
            "lon": "longitude",
            "lat": "latitude",
            "time": "time",
            "depth": "depth",
        }  # same dimensions for all instruments
        self.add_bathymetry = add_bathymetry
        self.allow_time_extrapolation = allow_time_extrapolation
        self.verbose_progress = verbose_progress
        self.buffer_spec = buffer_spec
        self.limit_spec = limit_spec

    def load_input_data(self) -> FieldSet:
        """Load and return the input data as a FieldSet for the instrument."""
        try:
            fieldset = self._generate_fieldset()
        except Exception as e:
            raise CopernicusCatalogueError(
                f"Failed to load input data directly from Copernicus Marine (or local data) for instrument '{self.name}'. Original error: {e}"
            ) from e

        # interpolation methods
        for var in (v for v in self.variables if v not in ("U", "V")):
            getattr(fieldset, var).interp_method = "linear_invdist_land_tracer"

        # depth negative
        for g in fieldset.gridset.grids:
            g.negate_depth()

        # bathymetry data
        if self.add_bathymetry:
            bathymetry_field = _get_bathy_data(
                self.expedition.schedule.space_time_region,
                latlon_buffer=self.buffer_spec.get("latlon")
                if self.buffer_spec
                else None,
                from_data=self.from_data,
            ).bathymetry
            bathymetry_field.data = -bathymetry_field.data
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
        if not self.verbose_progress:
            with yaspin(
                text=f"Simulating {self.name} measurements... ",
                side="right",
                spinner=ship_spinner,
            ) as spinner:
                self.simulate(measurements, out_path)
                spinner.ok("✅\n")
        else:
            print(f"Simulating {self.name} measurements... ")
            self.simulate(measurements, out_path)
            print("\n")

    def _get_copernicus_ds(
        self,
        physical: bool,
        var: str,
    ) -> xr.Dataset:
        """Get Copernicus Marine dataset for direct ingestion."""
        product_id = _select_product_id(
            physical=physical,
            schedule_start=self.expedition.schedule.space_time_region.time_range.start_time,
            schedule_end=self.expedition.schedule.space_time_region.time_range.end_time,
            variable=var if not physical else None,
        )

        latlon_buffer = self._get_spec_value("buffer", "latlon", 0.0)
        time_buffer = self._get_spec_value("buffer", "time", 0.0)
        depth_min = self._get_spec_value("limit", "depth_min", None)
        depth_max = self._get_spec_value("limit", "depth_max", None)

        return copernicusmarine.open_dataset(
            dataset_id=product_id,
            minimum_longitude=self.expedition.schedule.space_time_region.spatial_range.minimum_longitude
            - latlon_buffer,
            maximum_longitude=self.expedition.schedule.space_time_region.spatial_range.maximum_longitude
            + latlon_buffer,
            minimum_latitude=self.expedition.schedule.space_time_region.spatial_range.minimum_latitude
            - latlon_buffer,
            maximum_latitude=self.expedition.schedule.space_time_region.spatial_range.maximum_latitude
            + latlon_buffer,
            variables=[var],
            start_datetime=self.expedition.schedule.space_time_region.time_range.start_time,
            end_datetime=self.expedition.schedule.space_time_region.time_range.end_time
            + timedelta(days=time_buffer),
            minimum_depth=depth_min,
            maximum_depth=depth_max,
            coordinates_selection_method="outside",
        )

    def _load_local_ds(self, filename) -> xr.Dataset:
        """
        Load local dataset from specified data directory.

        Sliced according to expedition.schedule.space_time_region and buffer specs.
        """
        ds = xr.open_dataset(self.from_data.joinpath(filename))

        coord_rename = {}
        if "lat" in ds.coords:
            coord_rename["lat"] = "latitude"
        if "lon" in ds.coords:
            coord_rename["lon"] = "longitude"
        if coord_rename:
            ds = ds.rename(coord_rename)

        min_lon = (
            self.expedition.schedule.space_time_region.spatial_range.minimum_longitude
            - self._get_spec_value(
                "buffer", "latlon", 3.0
            )  # always add min 3 deg buffer for local data to avoid edge issues with ds.sel()
        )
        max_lon = (
            self.expedition.schedule.space_time_region.spatial_range.maximum_longitude
            + self._get_spec_value("buffer", "latlon", 3.0)
        )
        min_lat = (
            self.expedition.schedule.space_time_region.spatial_range.minimum_latitude
            - self._get_spec_value("buffer", "latlon", 3.0)
        )
        max_lat = (
            self.expedition.schedule.space_time_region.spatial_range.maximum_latitude
            + self._get_spec_value("buffer", "latlon", 3.0)
        )

        return ds.sel(
            latitude=slice(min_lat, max_lat),
            longitude=slice(min_lon, max_lon),
        )

    def _generate_fieldset(self) -> FieldSet:
        """
        Create and combine FieldSets for each variable, supporting both local and Copernicus Marine data sources.

        Avoids issues when using copernicusmarine and creating directly one FieldSet of ds's sourced from different Copernicus Marine product IDs, which is often the case for BGC variables.
        """
        fieldsets_list = []
        keys = list(self.variables.keys())

        for key in keys:
            var = self.variables[key]
            if self.from_data is not None:  # load from local data
                filename, full_var_name = _find_nc_file_with_variable(
                    self.from_data, var
                )
                ds = self._load_local_ds(filename)
                fs = FieldSet.from_xarray_dataset(
                    ds, {key: full_var_name}, self.dimensions, mesh="spherical"
                )
            else:  # steam via Copernicus Marine
                physical = var in COPERNICUSMARINE_PHYS_VARIABLES
                ds = self._get_copernicus_ds(physical=physical, var=var)
                fs = FieldSet.from_xarray_dataset(
                    ds, {key: var}, self.dimensions, mesh="spherical"
                )
            fieldsets_list.append(fs)

        base_fieldset = fieldsets_list[0]
        for fs, key in zip(fieldsets_list[1:], keys[1:], strict=False):
            base_fieldset.add_field(getattr(fs, key))

        return base_fieldset

    def _get_spec_value(self, spec_type: str, key: str, default=None):
        """Helper to extract a value from buffer_spec or limit_spec."""
        spec = self.buffer_spec if spec_type == "buffer" else self.limit_spec
        return spec.get(key) if spec and spec.get(key) is not None else default
