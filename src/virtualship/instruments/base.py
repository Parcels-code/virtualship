from __future__ import annotations

import abc
from collections import OrderedDict
from pathlib import Path
from typing import TYPE_CHECKING

import copernicusmarine
import xarray as xr
from yaspin import yaspin

from parcels import FieldSet
from parcels.interpolators import XLinearInvdistLandTracer
from virtualship.errors import CopernicusCatalogueError
from virtualship.utils import (
    BATHYMETRY_PRODUCT_ID,
    COPERNICUSMARINE_PHYS_VARIABLES,
    _find_files_in_timerange,
    _find_nc_file_with_variable,
    _select_product_id,
    ship_spinner,
)

if TYPE_CHECKING:
    from virtualship.models import Expedition


### TODO:

# TODO: not done anything for --from-data version!!!


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
        self.dimensions = {  # TODO, not needed in v4?!
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
        # TODO: this could be one method...?
        try:
            fieldset = self._generate_fieldset(add_bathymetry=self.add_bathymetry)
        except Exception as e:
            raise CopernicusCatalogueError(
                f"Failed to load input data directly from Copernicus Marine (or local data) for instrument '{self.__class__.__name__}'. Original error: {e}"
            ) from e

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
        instrument_name = self.__class__.__name__.split("Instrument")[0]
        if not self.verbose_progress:
            with yaspin(
                text=f"Simulating {instrument_name} measurements... ",
                side="right",
                spinner=ship_spinner,
            ) as spinner:
                self.simulate(measurements, out_path)
                spinner.ok("✅\n")
        else:
            print(f"Simulating {instrument_name} measurements... ")
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

        return copernicusmarine.open_dataset(dataset_id=product_id)

    def _generate_fieldset(self, add_bathymetry=False) -> FieldSet:
        """
        Create and combine FieldSets for each variable, supporting both local and Copernicus Marine data sources.

        Per variable avoids issues when using copernicusmarine and creating directly one FieldSet of ds's sourced from different Copernicus Marine product IDs, which is often the case for BGC variables.
        """
        fieldsets_list = []

        for key, var in self.variables.items():
            if self.from_data is not None:  # load from local data
                # TODO: very out of date! Not done anything for --from-data version!!!

                # TODO: if keeping --from-data, think of cleverer way of space_time_region...can remove and automate instead away from the public API?

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
                ds = self._get_copernicus_ds(physical=physical, var=var)[[var]]
                ds = ds.rename({var: key})

                # negate depth
                ds["depth"] = -ds["depth"]
                ds = ds.reindex(depth=ds.depth[::-1])
                ds.time.attrs["axis"] = "T"

                # add bathymetry if needed (only once)
                # easier to merge here as ds than later as FieldSet with no time dimension (Parcels wants 'T' axis)
                if add_bathymetry and key == list(self.variables.keys())[0]:  # noqa: RUF015
                    ds_bathymetry = copernicusmarine.open_dataset(
                        BATHYMETRY_PRODUCT_ID,
                    )
                    ds_bathymetry = ds_bathymetry.rename({"deptho": "bathymetry"})[
                        ["bathymetry"]
                    ]
                    ds_bathymetry["bathymetry"] = -ds_bathymetry["bathymetry"]
                    ds = xr.merge([ds, ds_bathymetry], join="inner")

                # to fieldset
                fs = FieldSet.from_copernicusmarine(ds)

                # add interpolation method
                if var not in ("uo", "vo"):
                    getattr(fs, key).interp_method = XLinearInvdistLandTracer

            fieldsets_list.append(fs)

        # build fieldset, from base fieldset (this way of combining avoids issues which can arise when combining from different Copernicus product IDs, especially BGC variables)
        base_fieldset = fieldsets_list[0]
        for fs, key in zip(
            fieldsets_list[1:], list(self.variables.keys())[1:], strict=False
        ):
            base_fieldset.add_field(getattr(fs, key))

        return base_fieldset

    def _get_spec_value(self, spec_type: str, key: str, default=None):
        """Helper to extract a value from spacetime_buffer_size or limit_spec."""
        spec = self.spacetime_buffer_size if spec_type == "buffer" else self.limit_spec
        return spec.get(key) if spec and spec.get(key) is not None else default
