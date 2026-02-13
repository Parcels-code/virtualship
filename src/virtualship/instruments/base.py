from __future__ import annotations

import abc
from collections import OrderedDict
from datetime import timedelta
from itertools import pairwise
from pathlib import Path
from typing import TYPE_CHECKING

import copernicusmarine
import xarray as xr
from parcels import FieldSet
from yaspin import yaspin

from virtualship.errors import CopernicusCatalogueError
from virtualship.utils import (
    COPERNICUSMARINE_PHYS_VARIABLES,
    _find_files_in_timerange,
    _find_nc_file_with_variable,
    _get_bathy_data,
    _get_waypoint_latlons,
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
                self.min_lat,
                self.max_lat,
                self.min_lon,
                self.max_lon,
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

        latlon_buffer = self._get_spec_value(
            "buffer", "latlon", 0.25
        )  # [degrees]; default 0.25 deg buffer to ensure coverage in field cell edge cases
        depth_min = self._get_spec_value("limit", "depth_min", None)
        depth_max = self._get_spec_value("limit", "depth_max", None)
        spatial_constraint = self._get_spec_value("limit", "spatial", True)

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
        )

    def _generate_fieldset(self) -> FieldSet:
        """
        Create and combine FieldSets for each variable, supporting both local and Copernicus Marine data sources.

        Per variable avoids issues when using copernicusmarine and creating directly one FieldSet of ds's sourced from different Copernicus Marine product IDs, which is often the case for BGC variables.
        """
        fieldsets_list = []
        keys = list(self.variables.keys())

        time_buffer = self._get_spec_value("buffer", "time", 0.0)

        for key in keys:
            var = self.variables[key]
            if self.from_data is not None:  # load from local data
                physical = var in COPERNICUSMARINE_PHYS_VARIABLES
                if physical:
                    data_dir = self.from_data.joinpath("phys")
                else:
                    data_dir = self.from_data.joinpath("bgc")

                files = _find_files_in_timerange(
                    data_dir,
                    self.min_time,
                    self.max_time + timedelta(days=time_buffer),
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
                ds = self._get_copernicus_ds(
                    time_buffer,
                    physical=physical,
                    var=var,
                )
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
