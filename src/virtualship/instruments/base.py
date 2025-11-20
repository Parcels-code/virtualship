from __future__ import annotations

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
    _find_files_in_timerange,
    _find_nc_file_with_variable,
    _get_bathy_data,
    _select_product_id,
    ship_spinner,
)

if TYPE_CHECKING:
    from virtualship.models import Expedition


class Instrument(abc.ABC):
    """Base class for instruments and their simulation."""

    def __init__(
        self,
        expedition: Expedition,
        variables: dict,
        add_bathymetry: bool,
        allow_time_extrapolation: bool,
        verbose_progress: bool,
        from_data: Path | None,
        spacetime_buffer_size: dict | None = None,
        limit_spec: dict | None = None,
    ):
        """Initialise instrument."""
        self.expedition = expedition
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
        self.spacetime_buffer_size = spacetime_buffer_size
        self.limit_spec = limit_spec

    def load_input_data(self) -> FieldSet:
        """Load and return the input data as a FieldSet for the instrument."""
        try:
            fieldset = self._generate_fieldset()
        except Exception as e:
            raise CopernicusCatalogueError(
                f"Failed to load input data directly from Copernicus Marine (or local data) for instrument '{self.__class__.__name__}'. Original error: {e}"
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
                latlon_buffer=self.spacetime_buffer_size.get("latlon")
                if self.spacetime_buffer_size
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
                text=f"Simulating {self.__class__.__name__.split('Instrument')[0]} measurements... ",
                side="right",
                spinner=ship_spinner,
            ) as spinner:
                self.simulate(measurements, out_path)
                spinner.ok("✅\n")
        else:
            print(
                f"Simulating {self.__class__.__name__.split('Instrument')[0]} measurements... "
            )
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

    def _generate_fieldset(self) -> FieldSet:
        """
        Create and combine FieldSets for each variable, supporting both local and Copernicus Marine data sources.

        Per variable avoids issues when using copernicusmarine and creating directly one FieldSet of ds's sourced from different Copernicus Marine product IDs, which is often the case for BGC variables.
        """
        fieldsets_list = []
        keys = list(self.variables.keys())

        for key in keys:
            var = self.variables[key]
            if self.from_data is not None:  # load from local data
                physical = var in COPERNICUSMARINE_PHYS_VARIABLES
                if physical:
                    data_dir = self.from_data.joinpath("phys")
                else:
                    data_dir = self.from_data.joinpath("bgc")

                schedule_start = (
                    self.expedition.schedule.space_time_region.time_range.start_time
                )
                schedule_end = (
                    self.expedition.schedule.space_time_region.time_range.end_time
                )

                files = _find_files_in_timerange(
                    data_dir,
                    schedule_start,
                    schedule_end,
                )

                _, full_var_name = _find_nc_file_with_variable(
                    data_dir, var
                )  # get full variable name from one of the files; var may only appear as substring in variable name in file

                ds = xr.open_mfdataset(
                    [data_dir.joinpath(f) for f in files]
                )  # using: ds --> .from_xarray_dataset seems more robust than .from_netcdf for handling different temporal resolutions for different variables ...

                fs = FieldSet.from_xarray_dataset(
                    ds,
                    variables={key: full_var_name},
                    dimensions=self.dimensions,
                    mesh="spherical",
                )
            else:  # stream via Copernicus Marine Service
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
        """Helper to extract a value from spacetime_buffer_size or limit_spec."""
        spec = self.spacetime_buffer_size if spec_type == "buffer" else self.limit_spec
        return spec.get(key) if spec and spec.get(key) is not None else default
