import abc
from collections.abc import Callable
from datetime import timedelta

import copernicusmarine
from parcels import Field, FieldSet
from yaspin import yaspin

from virtualship.models.space_time_region import SpaceTimeRegion
from virtualship.utils import ship_spinner

# TODO:
# Discussion: Should each instrument manage its own data files for modularity,
# or should we consolidate downloads to minimize file duplication across instruments?
# Consider starting with per-instrument files for simplicity, and refactor later if needed.


class InputDataset(abc.ABC):
    """Base class for instrument input datasets."""

    def __init__(
        self,
        name: str,
        latlon_buffer: float,
        datetime_buffer: float,
        min_depth: float,
        max_depth: float,
        data_dir: str,
        credentials: dict,
        space_time_region: SpaceTimeRegion,
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
        ...

    def download_data(self) -> None:
        """Download data for the instrument using copernicusmarine."""
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

        # TODO: this step could be achieved just at the init stage of each child class? Doesn't need to be a function...
        datasets_args = self.get_datasets_dict()

        for dataset in datasets_args.values():
            download_args = {**parameter_args, **dataset}
            copernicusmarine.subset(**download_args)


class Instrument(abc.ABC):
    """Base class for instruments and their simulation."""

    def __init__(
        self,
        config,
        schedule,
        input_dataset: InputDataset,
        kernels: list[Callable],
        filenames: dict,
        variables: dict,
        add_bathymetry: bool,
        allow_time_extrapolation: bool,
        bathymetry_file: str = "bathymetry.nc",
    ):
        """Initialise instrument."""
        self.config = config
        self.schedule = schedule
        self.input_data = input_dataset
        self.kernels = kernels
        self.name = input_dataset.name
        self.directory = input_dataset.data_dir
        self.filenames = filenames
        self.variables = variables
        self.dimensions = {
            "lon": "longitude",
            "lat": "latitude",
            "time": "time",
            "depth": "depth",
        }  # same dimensions for all instruments
        self.bathymetry_file = self.directory.joinpath(bathymetry_file)
        self.add_bathymetry = add_bathymetry
        self.allow_time_extrapolation = allow_time_extrapolation

    def load_input_data(self) -> FieldSet:
        """Load and return the input data as a FieldSet for the instrument."""
        fieldset = FieldSet.from_netcdf(
            self.filenames,
            self.variables,
            self.dimensions,
            allow_time_extrapolation=self.allow_time_extrapolation,
        )
        # interpolation methods
        for var in self.variables:
            getattr(fieldset, var).interp_method = "linear_invdist_land_tracer"
        # depth negative
        for g in fieldset.gridset.grids:
            g.negate_depth()
        # bathymetry data
        if self.add_bathymetry:
            bathymetry_field = Field.from_netcdf(
                self.bathymetry_file,
                self.bathymetry_variables,
                self.bathymetry_dimensions,
            )
            bathymetry_field.data = -bathymetry_field.data
            fieldset.add_field(bathymetry_field)
        fieldset.computeTimeChunk(0, 1)  # read in data already
        return fieldset

    @abc.abstractmethod
    def simulate(self):
        """Simulate instrument measurements."""
        ...

    def run(self):
        """Run instrument simulation."""
        with yaspin(
            text=f"Simulating {self.name} measurements... ",
            side="right",
            spinner=ship_spinner,
        ) as spinner:
            self.simulate()
            spinner.ok("✅")
