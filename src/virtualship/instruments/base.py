import abc
from datetime import timedelta
from pathlib import Path
from typing import TYPE_CHECKING

import copernicusmarine
import numpy as np
import xarray as xr
from parcels import FieldSet
from yaspin import yaspin

from virtualship.utils import (
    COPERNICUSMARINE_BGC_VARIABLES,
    COPERNICUSMARINE_PHYS_VARIABLES,
    _get_bathy_data,
    _select_product_id,
    ship_spinner,
)

if TYPE_CHECKING:
    from virtualship.models import Expedition


class Instrument(abc.ABC):
    """Base class for instruments and their simulation."""

    #! TODO List:
    # TODO: how is this handling credentials?! Seems to work already, are these set up from my previous instances of using copernicusmarine? Therefore users will only have to do it once too?

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
        buffer_spec: dict | None = None,
        limit_spec: dict | None = None,
    ):
        """Initialise instrument."""
        self.name = name
        self.expedition = expedition
        self.directory = directory
        self.filenames = filenames
        self.variables = variables
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
            datasets = []
            for var in self.variables.values():
                physical = True if var in COPERNICUSMARINE_PHYS_VARIABLES else False
                datasets.append(self._get_copernicus_ds(physical=physical, var=var))

            # make sure time dims are matched if BGC variables are present (different monthly/daily resolutions can impact fieldset_endtime in simulate)
            all_keys = set().union(*(ds.keys() for ds in datasets))
            if all_keys & set(COPERNICUSMARINE_BGC_VARIABLES):
                datasets = self._align_temporal(datasets)

            ds_concat = xr.merge(datasets)  # TODO: deal with WARNINGS?

            fieldset = FieldSet.from_xarray_dataset(
                ds_concat, self.variables, self.dimensions, mesh="spherical"
            )

        except Exception as e:
            raise FileNotFoundError(
                f"Failed to load input data directly from Copernicus Marine for instrument '{self.name}'. "
                f"Please check your credentials, network connection, and variable names. Original error: {e}"
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
            ).bathymetry
            bathymetry_field.data = -bathymetry_field.data
            fieldset.add_field(bathymetry_field)

        return fieldset

    @abc.abstractmethod
    def simulate(self, data_dir: Path, measurements: list, out_path: str | Path):
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

        latlon_buffer = self.buffer_spec.get("latlon") if self.buffer_spec else 0.0
        time_buffer = self.buffer_spec.get("time") if self.buffer_spec else 0.0

        depth_min = self.limit_spec.get("depth_min") if self.limit_spec else None
        depth_max = self.limit_spec.get("depth_max") if self.limit_spec else None

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

    def _align_temporal(self, datasets: list[xr.Dataset]) -> list[xr.Dataset]:
        """Align monthly and daily time dims of multiple datasets (by repeating monthly values daily)."""
        reference_time = datasets[
            np.argmax(ds.time for ds in datasets)
        ].time  # daily timeseries

        datasets_aligned = []
        for ds in datasets:
            if not np.array_equal(ds.time, reference_time):
                # TODO: NEED TO CHOOSE BEST METHOD HERE
                # ds = ds.resample(time="1D").ffill().reindex(time=reference_time)
                # ds = ds.resample(time="1D").ffill()
                ds = ds.reindex({"time": reference_time}, method="nearest")
            datasets_aligned.append(ds)

        return datasets_aligned
