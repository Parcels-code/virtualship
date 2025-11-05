import abc
from datetime import timedelta
from pathlib import Path
from typing import TYPE_CHECKING

import copernicusmarine
import xarray as xr
from yaspin import yaspin

from parcels import Field, FieldSet
from virtualship.cli._fetch import get_existing_download, get_space_time_region_hash
from virtualship.utils import _select_product_id, ship_spinner

if TYPE_CHECKING:
    from virtualship.models import Expedition, SpaceTimeRegion


class InputDataset(abc.ABC):
    """Base class for instrument input datasets."""

    # TODO: data download is performed per instrument (in `fetch`), which is a bit inefficient when some instruments can share dataa.
    # TODO: However, future changes, with Parcels-v4 and copernicusmarine direct ingestion, will hopefully remove the need for fetch.

    def __init__(
        self,
        name: str,
        latlon_buffer: float,
        datetime_buffer: float,
        min_depth: float,
        max_depth: float,
        data_dir: str,
        credentials: dict,
        space_time_region: "SpaceTimeRegion",
    ):
        """Initialise input dataset."""
        self.name = name
        self.latlon_buffer = latlon_buffer
        self.datetime_buffer = datetime_buffer
        self.min_depth = min_depth
        self.max_depth = max_depth
        self.data_dir = data_dir
        self.credentials = credentials
        self.space_time_region = space_time_region

    @abc.abstractmethod
    def get_datasets_dict(self) -> dict:
        """Get parameters for instrument's variable(s) specific data download."""

    def download_data(self) -> None:
        """Download data for the instrument using copernicusmarine, with correct product ID selection."""
        parameter_args = dict(
            minimum_longitude=self.space_time_region.spatial_range.minimum_longitude
            - self.latlon_buffer,
            maximum_longitude=self.space_time_region.spatial_range.maximum_longitude
            + self.latlon_buffer,
            minimum_latitude=self.space_time_region.spatial_range.minimum_latitude
            - self.latlon_buffer,
            maximum_latitude=self.space_time_region.spatial_range.maximum_latitude
            + self.latlon_buffer,
            start_datetime=self.space_time_region.time_range.start_time,
            end_datetime=self.space_time_region.time_range.end_time
            + timedelta(days=self.datetime_buffer),
            minimum_depth=abs(self.min_depth),
            maximum_depth=abs(self.max_depth),
            output_directory=self.data_dir,
            username=self.credentials["username"],
            password=self.credentials["password"],
            overwrite=True,
            coordinates_selection_method="outside",
        )

        datasets_args = self.get_datasets_dict()

        for dataset in datasets_args.values():
            physical = dataset.get("physical")
            if physical:
                variable = None
            else:
                variable = dataset.get("variables")[0]  # BGC variables, special case

            dataset_id = _select_product_id(
                physical=physical,
                schedule_start=self.space_time_region.time_range.start_time,
                schedule_end=self.space_time_region.time_range.end_time,
                username=self.credentials["username"],
                password=self.credentials["password"],
                variable=variable,
            )
            download_args = {
                **parameter_args,
                **{k: v for k, v in dataset.items() if k != "physical"},
                "dataset_id": dataset_id,
            }
            copernicusmarine.subset(**download_args)


class Instrument(abc.ABC):
    """Base class for instruments and their simulation."""

    #! TODO List:
    # TODO: update documentation/quickstart
    # TODO: update tests
    # TODO: if use direct ingestion as primary data sourcing, can substantially cut code base (including _fetch.py, InputDataset objects). Consider this for Parcels v4 transition.

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
        from_copernicusmarine: bool = False,
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
        self.from_copernicusmarine = from_copernicusmarine

    def load_input_data(self) -> FieldSet:
        """Load and return the input data as a FieldSet for the instrument."""
        if self.from_copernicusmarine:
            try:
                datasets = []
                for var in self.variables.values():
                    physical = (
                        True if var in ("uo", "vo", "so", "thetao") else False
                    )  # TODO: add more if start using new physical variables! Or more dynamic way of determining?
                    ds = self._get_copernicus_ds(
                        physical=physical, var=var
                    )  # user should be prompted for credentials
                    datasets.append(ds)

                ds_concat = xr.merge(datasets)
                fieldset = FieldSet.from_xarray_dataset(
                    ds_concat, self.variables, self.dimensions, mesh="spherical"
                )

            except Exception as e:
                raise FileNotFoundError(
                    f"Failed to load input data directly from Copernicus Marine for instrument '{self.name}'. "
                    f"Please check your credentials, network connection, and variable names. Original error: {e}"
                ) from e

        else:  # from fetched data on disk
            try:
                data_dir = self._get_data_dir(self.directory)
                joined_filepaths = {
                    key: data_dir.joinpath(filename)
                    for key, filename in self.filenames.items()
                }
                fieldset = FieldSet.from_netcdf(
                    joined_filepaths,
                    self.variables,
                    self.dimensions,
                    allow_time_extrapolation=self.allow_time_extrapolation,
                )
            except FileNotFoundError as e:
                raise FileNotFoundError(
                    f"Input data for instrument {self.name} not found locally. Have you run the `virtualship fetch` command?"
                    "Alternatively, you can use the `--from-copernicusmarine` option to ingest data directly from Copernicus Marine."
                ) from e

        # interpolation methods
        for var in (v for v in self.variables if v not in ("U", "V")):
            getattr(fieldset, var).interp_method = "linear_invdist_land_tracer"
        # depth negative
        for g in fieldset.gridset.grids:
            g.negate_depth()
        # bathymetry data
        if self.add_bathymetry:
            bathymetry_field = Field.from_netcdf(
                data_dir.joinpath(self.bathymetry_file),
                variable=("bathymetry", "deptho"),
                dimensions={"lon": "longitude", "lat": "latitude"},
            )
            bathymetry_field.data = -bathymetry_field.data
            fieldset.add_field(bathymetry_field)
        fieldset.computeTimeChunk(0, 1)  # read in data already

        return fieldset

    @abc.abstractmethod
    def simulate(self, data_dir: Path, measurements: list, out_path: str | Path):
        """Simulate instrument measurements."""

    def run(self, measurements: list, out_path: str | Path) -> None:
        """Run instrument simulation."""
        # TODO: this will have to be able to handle the non-spinner/instead progress bar for drifters and argos!

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

    def _get_data_dir(self, expedition_dir: Path) -> Path:
        space_time_region_hash = get_space_time_region_hash(
            self.expedition.schedule.space_time_region
        )
        data_dir = get_existing_download(expedition_dir, space_time_region_hash)

        assert data_dir is not None, (
            "Input data hasn't been found. Have you run the `virtualship fetch` command?"
        )

        return data_dir

    def _get_copernicus_ds(self, physical: bool, var: str) -> xr.Dataset:
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
            variables=["uo", "vo", "so", "thetao"],
            start_datetime=self.expedition.schedule.space_time_region.time_range.start_time,
            end_datetime=self.expedition.schedule.space_time_region.time_range.end_time,
            coordinates_selection_method="outside",
        )
