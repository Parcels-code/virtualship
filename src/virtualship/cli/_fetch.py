from __future__ import annotations

import hashlib
import shutil
from datetime import datetime
from pathlib import Path
from typing import TYPE_CHECKING

import copernicusmarine
from copernicusmarine.core_functions.credentials_utils import InvalidUsernameOrPassword
from pydantic import BaseModel

from virtualship.errors import IncompleteDownloadError
from virtualship.utils import (
    _dump_yaml,
    _generic_load_yaml,
    _get_expedition,
    get_input_dataset_class,
)

if TYPE_CHECKING:
    from virtualship.models import SpaceTimeRegion

import click

import virtualship.cli._creds as creds
from virtualship.utils import EXPEDITION

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
    # ################################# TEMPORARY TIMER: START #################################
    import time

    start_time = time.time()
    print("[TIMER] Expedition started...")
    # ################################# TEMPORARY TIMER: START #################################

    if sum([username is None, password is None]) == 1:
        raise ValueError("Both username and password must be provided when using CLI.")

    path = Path(path)

    data_dir = path / "data"
    data_dir.mkdir(exist_ok=True)

    expedition = _get_expedition(path)

    expedition.schedule.verify(
        expedition.ship_config.ship_speed_knots,
        bathy_data_dir=None,
        check_space_time_region=True,
        ignore_missing_bathymetry=True,
    )

    space_time_region_hash = get_space_time_region_hash(
        expedition.schedule.space_time_region
    )

    existing_download = get_existing_download(data_dir, space_time_region_hash)
    if existing_download is not None:
        click.echo(
            f"Data download for space-time region already completed ('{existing_download}')."
        )
        return

    creds_path = path / creds.CREDENTIALS_FILE
    credentials = {}
    credentials["username"], credentials["password"] = creds.get_credentials_flow(
        username, password, creds_path
    )

    # Extract instruments and space_time_region details from expedition
    instruments_in_expedition = expedition.get_instruments()
    space_time_region = expedition.schedule.space_time_region

    # Create download folder and set download metadata
    download_folder = data_dir / hash_to_filename(space_time_region_hash)
    download_folder.mkdir()
    DownloadMetadata(download_complete=False).to_yaml(
        download_folder / DOWNLOAD_METADATA
    )
    shutil.copyfile(path / EXPEDITION, download_folder / EXPEDITION)

    click.echo(f"\n\n{(' Fetching data for: Bathymetry ').center(80, '=')}\n\n")

    # bathymetry (for all expeditions)
    copernicusmarine.subset(
        dataset_id="cmems_mod_glo_phy_my_0.083deg_static",
        variables=["deptho"],
        minimum_longitude=space_time_region.spatial_range.minimum_longitude,
        maximum_longitude=space_time_region.spatial_range.maximum_longitude,
        minimum_latitude=space_time_region.spatial_range.minimum_latitude,
        maximum_latitude=space_time_region.spatial_range.maximum_latitude,
        start_datetime=space_time_region.time_range.start_time,
        end_datetime=space_time_region.time_range.start_time,
        minimum_depth=abs(space_time_region.spatial_range.minimum_depth),
        maximum_depth=abs(space_time_region.spatial_range.maximum_depth),
        output_filename="bathymetry.nc",
        output_directory=download_folder,
        username=credentials["username"],
        password=credentials["password"],
        overwrite=True,
        coordinates_selection_method="outside",
    )

    # download, only instruments present in the expedition
    for itype in instruments_in_expedition:
        input_dataset_class = get_input_dataset_class(itype)
        if input_dataset_class is None:
            raise RuntimeError(f"No input dataset class found for type {itype}.")
        click.echo(
            f"\n\n{(' Fetching data for: ' + itype.value + ' ').center(80, '=')}\n\n"
        )
        try:
            input_dataset = input_dataset_class(
                data_dir=download_folder,
                credentials=credentials,
                space_time_region=space_time_region,
            )
            input_dataset.download_data()
        except InvalidUsernameOrPassword as e:
            shutil.rmtree(download_folder)
            raise e
        click.echo(f"{itype.value} data download completed.")

    complete_download(download_folder)

    ################################# TEMPORARY TIMER: END #################################
    end_time = time.time()
    elapsed = end_time - start_time
    print(f"[TIMER] Expedition completed in {elapsed:.2f} seconds.")
    ################################# TEMPORARY TIMER: END #################################


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


def get_existing_download(data_dir: Path, space_time_region_hash: str) -> Path | None:
    """Check if a download has already been completed. If so, return the path for existing download."""
    for download_path in data_dir.rglob("*"):
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
