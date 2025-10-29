import abc
from datetime import timedelta
from pathlib import Path

import copernicusmarine
import numpy as np

from parcels import Field, FieldSet
from virtualship.cli._fetch import get_existing_download, get_space_time_region_hash
from virtualship.errors import CopernicusCatalogueError
from virtualship.models import Expedition, SpaceTimeRegion

PRODUCT_IDS = {
    "phys": {
        "reanalysis": "cmems_mod_glo_phy_my_0.083deg_P1D-m",
        "reanalysis_interim": "cmems_mod_glo_phy_myint_0.083deg_P1D-m",
        "analysis": "cmems_mod_glo_phy_anfc_0.083deg_P1D-m",
    },
    "bgc": {
        "reanalysis": "cmems_mod_glo_bgc_my_0.25deg_P1D-m",
        "reanalysis_interim": "cmems_mod_glo_bgc_myint_0.25deg_P1D-m",
        "analysis": None,  # will be set per variable
    },
}

BGC_ANALYSIS_IDS = {
    "o2": "cmems_mod_glo_bgc-bio_anfc_0.25deg_P1D-m",
    "chl": "cmems_mod_glo_bgc-pft_anfc_0.25deg_P1D-m",
    "no3": "cmems_mod_glo_bgc-nut_anfc_0.25deg_P1D-m",
    "po4": "cmems_mod_glo_bgc-nut_anfc_0.25deg_P1D-m",
    "ph": "cmems_mod_glo_bgc-car_anfc_0.25deg_P1D-m",
    "phyc": "cmems_mod_glo_bgc-pft_anfc_0.25deg_P1D-m",
    "nppv": "cmems_mod_glo_bgc-bio_anfc_0.25deg_P1D-m",
}

MONTHLY_BGC_REANALYSIS_IDS = {
    "ph": "cmems_mod_glo_bgc_my_0.25deg_P1M-m",
    "phyc": "cmems_mod_glo_bgc_my_0.25deg_P1M-m",
}
MONTHLY_BGC_REANALYSIS_INTERIM_IDS = {
    "ph": "cmems_mod_glo_bgc_myint_0.25deg_P1M-m",
    "phyc": "cmems_mod_glo_bgc_myint_0.25deg_P1M-m",
}


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

            dataset_id = self._select_product_id(
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

    def _select_product_id(
        self,
        physical: bool,
        schedule_start,
        schedule_end,
        username: str,
        password: str,
        variable: str | None = None,
    ) -> str:
        """Determine which copernicus product id should be selected (reanalysis, reanalysis-interim, analysis & forecast), for prescribed schedule and physical vs. BGC."""
        key = "phys" if physical else "bgc"
        selected_id = None

        for period, pid in PRODUCT_IDS[key].items():
            # for BGC analysis, set pid per variable
            if key == "bgc" and period == "analysis":
                if variable is None or variable not in BGC_ANALYSIS_IDS:
                    continue
                pid = BGC_ANALYSIS_IDS[variable]
            # for BGC reanalysis, check if requires monthly product
            if (
                key == "bgc"
                and period == "reanalysis"
                and variable in MONTHLY_BGC_REANALYSIS_IDS
            ):
                monthly_pid = MONTHLY_BGC_REANALYSIS_IDS[variable]
                ds_monthly = copernicusmarine.open_dataset(
                    monthly_pid,
                    username=username,
                    password=password,
                )
                time_end_monthly = ds_monthly["time"][-1].values
                if np.datetime64(schedule_end) <= time_end_monthly:
                    pid = monthly_pid
            # for BGC reanalysis_interim, check if requires monthly product
            if (
                key == "bgc"
                and period == "reanalysis_interim"
                and variable in MONTHLY_BGC_REANALYSIS_INTERIM_IDS
            ):
                monthly_pid = MONTHLY_BGC_REANALYSIS_INTERIM_IDS[variable]
                ds_monthly = copernicusmarine.open_dataset(
                    monthly_pid, username=username, password=password
                )
                time_end_monthly = ds_monthly["time"][-1].values
                if np.datetime64(schedule_end) <= time_end_monthly:
                    pid = monthly_pid
            if pid is None:
                continue
            ds = copernicusmarine.open_dataset(
                pid, username=username, password=password
            )
            time_end = ds["time"][-1].values
            if np.datetime64(schedule_end) <= time_end:
                selected_id = pid
                break

        if selected_id is None:
            raise CopernicusCatalogueError(
                "No suitable product found in the Copernicus Marine Catalogue for the scheduled time and variable."
            )

        def start_end_in_product_timerange(
            selected_id, schedule_start, schedule_end, username, password
        ):
            ds_selected = copernicusmarine.open_dataset(
                selected_id, username=username, password=password
            )
            time_values = ds_selected["time"].values
            import numpy as np

            time_min, time_max = np.min(time_values), np.max(time_values)
            return (
                np.datetime64(schedule_start) >= time_min
                and np.datetime64(schedule_end) <= time_max
            )

        if start_end_in_product_timerange(
            selected_id, schedule_start, schedule_end, username, password
        ):
            return selected_id
        else:
            return (
                PRODUCT_IDS["phys"]["analysis"]
                if physical
                else BGC_ANALYSIS_IDS[variable]
            )


class Instrument(abc.ABC):
    """Base class for instruments and their simulation."""

    def __init__(
        self,
        name: str,
        expedition: Expedition,
        directory: Path | str,
        filenames: dict,
        variables: dict,
        add_bathymetry: bool,
        allow_time_extrapolation: bool,
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

    def load_input_data(self) -> FieldSet:
        """Load and return the input data as a FieldSet for the instrument."""
        # TODO: can simulate_schedule.py be refactored to be contained in base.py and repsective instrument files too...?
        # TODO: tests need updating...!

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
                f"Input data for instrument {self.name} not found. Have you run the `virtualship fetch` command??"
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

        # with yaspin(
        #     text=f"Simulating {self.name} measurements... ",
        #     side="right",
        #     spinner=ship_spinner,
        # ) as spinner:
        self.simulate(measurements, out_path)
        # spinner.ok("✅")

    def _get_data_dir(self, expedition_dir: Path) -> Path:
        space_time_region_hash = get_space_time_region_hash(
            self.expedition.schedule.space_time_region
        )
        data_dir = get_existing_download(expedition_dir, space_time_region_hash)

        assert data_dir is not None, (
            "Input data hasn't been found. Have you run the `virtualship fetch` command?"
        )

        return data_dir
