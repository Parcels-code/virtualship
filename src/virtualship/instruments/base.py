import abc
from datetime import timedelta
from pathlib import Path
from typing import TYPE_CHECKING

import copernicusmarine
import numpy as np
import xarray as xr
from yaspin import yaspin

from parcels import FieldSet
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
    # TODO: update documentation/quickstart
    # TODO: update tests
    #! TODO: how is this handling credentials?! Seems to work already, are these set up from my previous instances of using copernicusmarine? Therefore users will only have to do it once too?

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
        bathymetry_file: str = "bathymetry.nc",
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
        self.bathymetry_file = bathymetry_file
        self.add_bathymetry = add_bathymetry
        self.allow_time_extrapolation = allow_time_extrapolation
        self.verbose_progress = verbose_progress

    def load_input_data(self) -> FieldSet:
        """Load and return the input data as a FieldSet for the instrument."""
        try:
            datasets = []
            for var in self.variables.values():
                physical = True if var in COPERNICUSMARINE_PHYS_VARIABLES else False

                # TODO: TEMPORARY BODGE FOR DRIFTER INSTRUMENT - REMOVE WHEN ABLE TO!
                if self.name == "Drifter":
                    ds = self._get_copernicus_ds_DRIFTER(physical=physical, var=var)
                else:
                    ds = self._get_copernicus_ds(physical=physical, var=var)
                datasets.append(ds)

            # make sure time dims are matched if BGC variables are present (different monthly/daily resolutions can impact fieldset_endtime in simulate)
            if any(
                key in COPERNICUSMARINE_BGC_VARIABLES
                for key in ds.keys()
                for ds in datasets
            ):
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
        bathymetry_field = _get_bathy_data(
            self.expedition.schedule.space_time_region
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

        # self.simulate(measurements, out_path)

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

        return copernicusmarine.open_dataset(
            dataset_id=product_id,
            dataset_part="default",
            minimum_longitude=self.expedition.schedule.space_time_region.spatial_range.minimum_longitude,
            maximum_longitude=self.expedition.schedule.space_time_region.spatial_range.maximum_longitude,
            minimum_latitude=self.expedition.schedule.space_time_region.spatial_range.minimum_latitude,
            maximum_latitude=self.expedition.schedule.space_time_region.spatial_range.maximum_latitude,
            variables=[var],
            start_datetime=self.expedition.schedule.space_time_region.time_range.start_time,
            end_datetime=self.expedition.schedule.space_time_region.time_range.end_time,
            coordinates_selection_method="outside",
        )

    # TODO: TEMPORARY BODGE FOR DRIFTER INSTRUMENT - REMOVE WHEN ABLE TO!
    def _get_copernicus_ds_DRIFTER(
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

        return copernicusmarine.open_dataset(
            dataset_id=product_id,
            dataset_part="default",
            minimum_longitude=self.expedition.schedule.space_time_region.spatial_range.minimum_longitude
            - 3.0,
            maximum_longitude=self.expedition.schedule.space_time_region.spatial_range.maximum_longitude
            + 3.0,
            minimum_latitude=self.expedition.schedule.space_time_region.spatial_range.minimum_latitude
            - 3.0,
            maximum_latitude=self.expedition.schedule.space_time_region.spatial_range.maximum_latitude
            + 3.0,
            maximum_depth=1.0,
            minimum_depth=1.0,
            variables=[var],
            start_datetime=self.expedition.schedule.space_time_region.time_range.start_time,
            end_datetime=self.expedition.schedule.space_time_region.time_range.end_time
            + timedelta(days=21.0),
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
