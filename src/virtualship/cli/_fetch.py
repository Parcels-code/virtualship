from __future__ import annotations

import hashlib
import shutil
from datetime import datetime, timedelta
from pathlib import Path
from typing import TYPE_CHECKING

import numpy as np
from pydantic import BaseModel

from virtualship.errors import CopernicusTimeRangeError, IncompleteDownloadError
from virtualship.utils import (
    _dump_yaml,
    _generic_load_yaml,
    _get_schedule,
    _get_ship_config,
)

if TYPE_CHECKING:
    from virtualship.models import SpaceTimeRegion

import click
import copernicusmarine
from copernicusmarine.core_functions.credentials_utils import InvalidUsernameOrPassword

import virtualship.cli._creds as creds
from virtualship.utils import SCHEDULE

DOWNLOAD_METADATA = "download_metadata.yaml"


def _fetch(path: str | Path, username: str | None, password: str | None) -> None:
    """
    Download input data for an expedition.

    Entrypoint for the tool to download data based on space-time region provided in the
    schedule file. Data is downloaded from Copernicus Marine, credentials for which can be
    obtained via registration: https://data.marine.copernicus.eu/register . Credentials can
    be provided on prompt, via command line arguments, or via a YAML config file. Run
    `virtualship fetch` on an expedition for more info.
    """
    from virtualship.models import InstrumentType

    if sum([username is None, password is None]) == 1:
        raise ValueError("Both username and password must be provided when using CLI.")

    path = Path(path)

    data_folder = path / "data"
    data_folder.mkdir(exist_ok=True)

    schedule = _get_schedule(path)
    ship_config = _get_ship_config(path)

    schedule.verify(
        ship_config.ship_speed_knots,
        input_data=None,
        check_space_time_region=True,
        ignore_missing_fieldsets=True,
    )

    space_time_region_hash = get_space_time_region_hash(schedule.space_time_region)

    existing_download = get_existing_download(data_folder, space_time_region_hash)
    if existing_download is not None:
        click.echo(
            f"Data download for space-time region already completed ('{existing_download}')."
        )
        return

    creds_path = path / creds.CREDENTIALS_FILE
    username, password = creds.get_credentials_flow(username, password, creds_path)

    # Extract space_time_region details from the schedule
    spatial_range = schedule.space_time_region.spatial_range
    time_range = schedule.space_time_region.time_range
    start_datetime = time_range.start_time
    end_datetime = time_range.end_time
    instruments_in_schedule = schedule.get_instruments()

    # Create download folder and set download metadata
    download_folder = data_folder / hash_to_filename(space_time_region_hash)
    download_folder.mkdir()
    DownloadMetadata(download_complete=False).to_yaml(
        download_folder / DOWNLOAD_METADATA
    )
    shutil.copyfile(path / SCHEDULE, download_folder / SCHEDULE)

    # data download
    if (
        (
            {"XBT", "CTD", "CDT_BGC", "SHIP_UNDERWATER_ST"}
            & set(instrument.name for instrument in instruments_in_schedule)
        )
        or ship_config.ship_underwater_st_config is not None
        or ship_config.adcp_config is not None
    ):
        print("Ship data will be downloaded. Please wait...")

        phys_product_id = select_product_id(
            physical=True,
            schedule_start=start_datetime,
            schedule_end=end_datetime,
            username=username,
            password=password,
        )

        # Define all ship datasets to download, including bathymetry
        download_dict = {
            "Bathymetry": {
                "dataset_id": "cmems_mod_glo_phy_my_0.083deg_static",
                "variables": ["deptho"],
                "output_filename": "bathymetry.nc",
            },
            "UVdata": {
                "dataset_id": phys_product_id,
                "variables": ["uo", "vo"],
                "output_filename": "ship_uv.nc",
            },
            "Sdata": {
                "dataset_id": phys_product_id,
                "variables": ["so"],
                "output_filename": "ship_s.nc",
            },
            "Tdata": {
                "dataset_id": phys_product_id,
                "variables": ["thetao"],
                "output_filename": "ship_t.nc",
            },
        }

        # Iterate over all datasets and download each based on space_time_region
        try:
            for dataset in download_dict.values():
                copernicusmarine.subset(
                    dataset_id=dataset["dataset_id"],
                    variables=dataset["variables"],
                    minimum_longitude=spatial_range.minimum_longitude,
                    maximum_longitude=spatial_range.maximum_longitude,
                    minimum_latitude=spatial_range.minimum_latitude,
                    maximum_latitude=spatial_range.maximum_latitude,
                    start_datetime=start_datetime,
                    end_datetime=end_datetime,
                    minimum_depth=abs(spatial_range.minimum_depth),
                    maximum_depth=abs(spatial_range.maximum_depth),
                    output_filename=dataset["output_filename"],
                    output_directory=download_folder,
                    username=username,
                    password=password,
                    overwrite=True,
                    coordinates_selection_method="outside",
                )
        except InvalidUsernameOrPassword as e:
            shutil.rmtree(download_folder)
            raise e

        click.echo("Ship data download based on space-time region completed.")

    if InstrumentType.DRIFTER in instruments_in_schedule:
        print("Drifter data will be downloaded. Please wait...")
        drifter_download_dict = {
            "UVdata": {
                "dataset_id": phys_product_id,
                "variables": ["uo", "vo"],
                "output_filename": "drifter_uv.nc",
            },
            "Tdata": {
                "dataset_id": phys_product_id,
                "variables": ["thetao"],
                "output_filename": "drifter_t.nc",
            },
        }

        # Iterate over all datasets and download each based on space_time_region
        try:
            for dataset in drifter_download_dict.values():
                copernicusmarine.subset(
                    dataset_id=dataset["dataset_id"],
                    variables=dataset["variables"],
                    minimum_longitude=spatial_range.minimum_longitude - 3.0,
                    maximum_longitude=spatial_range.maximum_longitude + 3.0,
                    minimum_latitude=spatial_range.minimum_latitude - 3.0,
                    maximum_latitude=spatial_range.maximum_latitude + 3.0,
                    start_datetime=start_datetime,
                    end_datetime=end_datetime + timedelta(days=21),
                    minimum_depth=abs(1),
                    maximum_depth=abs(1),
                    output_filename=dataset["output_filename"],
                    output_directory=download_folder,
                    username=username,
                    password=password,
                    overwrite=True,
                    coordinates_selection_method="outside",
                )
        except InvalidUsernameOrPassword as e:
            shutil.rmtree(download_folder)
            raise e

        click.echo("Drifter data download based on space-time region completed.")

    if InstrumentType.ARGO_FLOAT in instruments_in_schedule:
        print("Argo float data will be downloaded. Please wait...")
        argo_download_dict = {
            "UVdata": {
                "dataset_id": phys_product_id,
                "variables": ["uo", "vo"],
                "output_filename": "argo_float_uv.nc",
            },
            "Sdata": {
                "dataset_id": phys_product_id,
                "variables": ["so"],
                "output_filename": "argo_float_s.nc",
            },
            "Tdata": {
                "dataset_id": phys_product_id,
                "variables": ["thetao"],
                "output_filename": "argo_float_t.nc",
            },
        }

        # Iterate over all datasets and download each based on space_time_region
        try:
            for dataset in argo_download_dict.values():
                copernicusmarine.subset(
                    dataset_id=dataset["dataset_id"],
                    variables=dataset["variables"],
                    minimum_longitude=spatial_range.minimum_longitude - 3.0,
                    maximum_longitude=spatial_range.maximum_longitude + 3.0,
                    minimum_latitude=spatial_range.minimum_latitude - 3.0,
                    maximum_latitude=spatial_range.maximum_latitude + 3.0,
                    start_datetime=start_datetime,
                    end_datetime=end_datetime + timedelta(days=21),
                    minimum_depth=abs(1),
                    maximum_depth=abs(spatial_range.maximum_depth),
                    output_filename=dataset["output_filename"],
                    output_directory=download_folder,
                    username=username,
                    password=password,
                    overwrite=True,
                    coordinates_selection_method="outside",
                )
        except InvalidUsernameOrPassword as e:
            shutil.rmtree(download_folder)
            raise e

        click.echo("Argo_float data download based on space-time region completed.")

    if InstrumentType.CTD_BGC in instruments_in_schedule:
        print("CTD_BGC data will be downloaded. Please wait...")

        bgc_args = {
            "physical": False,
            "schedule_start": start_datetime,
            "schedule_end": end_datetime,
            "username": username,
            "password": password,
        }

        ctd_bgc_download_dict = {
            "o2data": {
                "dataset_id": select_product_id(**{**bgc_args, "variable": "o2"}),
                "variables": ["o2"],
                "output_filename": "ctd_bgc_o2.nc",
            },
            "chlorodata": {
                "dataset_id": select_product_id(**{**bgc_args, "variable": "chl"}),
                "variables": ["chl"],
                "output_filename": "ctd_bgc_chl.nc",
            },
            "nitratedata": {
                "dataset_id": select_product_id(**{**bgc_args, "variable": "no3"}),
                "variables": ["no3"],
                "output_filename": "ctd_bgc_no3.nc",
            },
            "phosphatedata": {
                "dataset_id": select_product_id(**{**bgc_args, "variable": "po4"}),
                "variables": ["po4"],
                "output_filename": "ctd_bgc_po4.nc",
            },
            "phdata": {
                "dataset_id": select_product_id(
                    **{**bgc_args, "variable": "ph"}
                ),  # this will be monthly resolution if reanalysis(_interim) period
                "variables": ["ph"],
                "output_filename": "ctd_bgc_ph.nc",
            },
            "phytoplanktondata": {
                "dataset_id": select_product_id(
                    **{**bgc_args, "variable": "phyc"}
                ),  # this will be monthly resolution if reanalysis(_interim) period,
                "variables": ["phyc"],
                "output_filename": "ctd_bgc_phyc.nc",
            },
            "primaryproductiondata": {
                "dataset_id": select_product_id(**{**bgc_args, "variable": "nppv"}),
                "variables": ["nppv"],
                "output_filename": "ctd_bgc_nppv.nc",
            },
        }

        # Iterate over all datasets and download each based on space_time_region
        try:
            for dataset in ctd_bgc_download_dict.values():
                copernicusmarine.subset(
                    dataset_id=dataset["dataset_id"],
                    variables=dataset["variables"],
                    minimum_longitude=spatial_range.minimum_longitude - 3.0,
                    maximum_longitude=spatial_range.maximum_longitude + 3.0,
                    minimum_latitude=spatial_range.minimum_latitude - 3.0,
                    maximum_latitude=spatial_range.maximum_latitude + 3.0,
                    start_datetime=start_datetime,
                    end_datetime=end_datetime + timedelta(days=21),
                    minimum_depth=abs(1),
                    maximum_depth=abs(spatial_range.maximum_depth),
                    output_filename=dataset["output_filename"],
                    output_directory=download_folder,
                    username=username,
                    password=password,
                    overwrite=True,
                    coordinates_selection_method="outside",
                )
        except InvalidUsernameOrPassword as e:
            shutil.rmtree(download_folder)
            raise e

        click.echo("CTD_BGC data download based on space-time region completed.")

    complete_download(download_folder)


def _hash(s: str, *, length: int) -> str:
    """Create a hash of a string."""
    assert length % 2 == 0, "Length must be even."
    half_length = length // 2

    return hashlib.shake_128(s.encode("utf-8")).hexdigest(half_length)


def create_hash(s: str) -> str:
    """Create an 8 digit hash of a string."""
    return _hash(s, length=8)


def hash_model(model: BaseModel, salt: int = 0) -> str:
    """
    Hash a Pydantic model.

    :param region: The region to hash.
    :param salt: Salt to add to the hash.
    :returns: The hash.
    """
    return create_hash(model.model_dump_json() + str(salt))


def get_space_time_region_hash(space_time_region: SpaceTimeRegion) -> str:
    # Increment salt in the event of breaking data fetching changes with prior versions
    # of virtualship where you want to force new hashes (i.e., new data downloads)
    salt = 0
    return hash_model(space_time_region, salt=salt)


def filename_to_hash(filename: str) -> str:
    """Extract hash from filename of the format YYYYMMDD_HHMMSS_{hash}."""
    parts = filename.split("_")
    if len(parts) != 3:
        raise ValueError(
            f"Filename '{filename}' must have 3 parts delimited with underscores."
        )
    return parts[-1]


def hash_to_filename(hash: str) -> str:
    """Return a filename of the format YYYYMMDD_HHMMSS_{hash}."""
    if "_" in hash:
        raise ValueError("Hash cannot contain underscores.")
    return f"{datetime.now().strftime('%Y%m%d_%H%M%S')}_{hash}"


class DownloadMetadata(BaseModel):
    """Metadata for a data download."""

    download_complete: bool
    download_date: datetime | None = None

    def to_yaml(self, file_path: str | Path) -> None:
        with open(file_path, "w") as file:
            _dump_yaml(self, file)

    @classmethod
    def from_yaml(cls, file_path: str | Path) -> DownloadMetadata:
        return _generic_load_yaml(file_path, cls)


def get_existing_download(
    data_folder: Path, space_time_region_hash: str
) -> Path | None:
    """Check if a download has already been completed. If so, return the path for existing download."""
    for download_path in data_folder.rglob("*"):
        try:
            hash = filename_to_hash(download_path.name)
        except ValueError:
            continue

        if hash == space_time_region_hash:
            assert_complete_download(download_path)
            return download_path

    return None


def assert_complete_download(download_path: Path) -> None:
    download_metadata = download_path / DOWNLOAD_METADATA
    try:
        with open(download_metadata) as file:
            assert DownloadMetadata.from_yaml(file).download_complete
    except (FileNotFoundError, AssertionError) as e:
        raise IncompleteDownloadError(
            f"Download at {download_path} was found, but looks to be incomplete "
            f"(likely due to interupting it mid-download). Please delete this folder and retry."
        ) from e
    return


def complete_download(download_path: Path) -> None:
    """Mark a download as complete."""
    download_metadata = download_path / DOWNLOAD_METADATA
    metadata = DownloadMetadata(download_complete=True, download_date=datetime.now())
    metadata.to_yaml(download_metadata)
    return


def select_product_id(
    physical: bool,
    schedule_start: datetime,
    schedule_end: datetime,
    username: str,
    password: str,
    variable: str | None = None,  # only needed for BGC datasets
) -> str:
    """
    Determine which copernicus product id should be selected (reanalysis, reanalysis-interim, analysis & forecast), for prescribed schedule and physical vs. BGC.

    BGC is more complicated than physical products. Often (re)analysis period and variable dependent, hence more custom logic here.
    """
    product_ids = {
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

    bgc_analysis_ids = {
        "o2": "cmems_mod_glo_bgc-bio_anfc_0.25deg_P1D-m",
        "chl": "cmems_mod_glo_bgc-pft_anfc_0.25deg_P1D-m",
        "no3": "cmems_mod_glo_bgc-nut_anfc_0.25deg_P1D-m",
        "po4": "cmems_mod_glo_bgc-nut_anfc_0.25deg_P1D-m",
        "ph": "cmems_mod_glo_bgc-car_anfc_0.25deg_P1D-m",
        "phyc": "cmems_mod_glo_bgc-pft_anfc_0.25deg_P1D-m",
        "nppv": "cmems_mod_glo_bgc-bio_anfc_0.25deg_P1D-m",
    }

    # pH and phytoplankton variables are available as *monthly* products only in renalysis(_interim) period
    monthly_bgc_reanalysis_ids = {
        "ph": "cmems_mod_glo_bgc_my_0.25deg_P1M-m",
        "phyc": "cmems_mod_glo_bgc_my_0.25deg_P1M-m",
    }
    monthly_bgc_reanalysis_interim_ids = {
        "ph": "cmems_mod_glo_bgc_myint_0.25deg_P1M-m",
        "phyc": "cmems_mod_glo_bgc_myint_0.25deg_P1M-m",
    }

    key = "phys" if physical else "bgc"
    selected_id = None

    for period, pid in product_ids[key].items():
        # for BGC analysis, set pid per variable
        if key == "bgc" and period == "analysis":
            if variable is None or variable not in bgc_analysis_ids:
                continue
            pid = bgc_analysis_ids[variable]
        # for BGC reanalysis, check if requires monthly product
        if (
            key == "bgc"
            and period == "reanalysis"
            and variable in monthly_bgc_reanalysis_ids
        ):
            monthly_pid = monthly_bgc_reanalysis_ids[variable]
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
            and variable in monthly_bgc_reanalysis_interim_ids
        ):
            monthly_pid = monthly_bgc_reanalysis_interim_ids[variable]
            ds_monthly = copernicusmarine.open_dataset(
                monthly_pid, username=username, password=password
            )
            time_end_monthly = ds_monthly["time"][-1].values
            if np.datetime64(schedule_end) <= time_end_monthly:
                pid = monthly_pid
        if pid is None:
            continue
        ds = copernicusmarine.open_dataset(pid, username=username, password=password)
        time_end = ds["time"][-1].values
        if np.datetime64(schedule_end) <= time_end:
            selected_id = pid
            break

    if selected_id is None:
        raise ValueError(
            "No suitable product found in the Copernicus Marine Catalogue for the scheduled time and variable."
        )

    # confirm full schedule (start and end) is in the selected product's time range
    schedule_in_product_timerange(
        selected_id, schedule_start, schedule_end, username, password
    )

    return selected_id


def schedule_in_product_timerange(
    selected_id: str,
    schedule_start: datetime,
    schedule_end: datetime,
    username: str,
    password: str,
) -> None:
    """Raise error if schedule_start and schedule_end are not both within a selected Copernicus product's time range."""
    ds_selected = copernicusmarine.open_dataset(
        selected_id, username=username, password=password
    )
    time_values = ds_selected["time"].values
    time_min = np.min(time_values)
    time_max = np.max(time_values)

    if not (
        np.datetime64(schedule_start) >= time_min
        and np.datetime64(schedule_end) <= time_max
    ):
        raise CopernicusTimeRangeError(
            f"\n\n⚠️  Schedule start ({schedule_start}) and end ({schedule_end}) span different product IDs from the Copernicus Marine Catalogue.  ⚠️"
            "\n\nUnfortunately, this rare situation is not currently supported in VirtualShip."
            "\n\nSee the following link for more information and guidance on how to fix: [<<< INSERT LINK >>>]"  # TODO: ADD LINK when written the documentation!
            f"\n\nSelected product '{selected_id}' covers {time_min} to {time_max}."
            "\n\nPlease use the 'virtualship plan` tool to re-adjust your schedule, or manually edit the schedule.yaml and ship_config.yaml files."
        )
