from __future__ import annotations

import os
import warnings
from datetime import timedelta
from functools import lru_cache
from importlib.resources import files
from pathlib import Path
from typing import TYPE_CHECKING, TextIO

if TYPE_CHECKING:
    from virtualship.models import Expedition

import pandas as pd
import yaml
from pydantic import BaseModel
from yaspin import Spinner

EXPEDITION = "expedition.yaml"
CHECKPOINT = "checkpoint.yaml"


def load_static_file(name: str) -> str:
    """Load static file from the ``virtualship.static`` module by file name."""
    return files("virtualship.static").joinpath(name).read_text(encoding="utf-8")


@lru_cache(None)
@lru_cache(None)
def get_example_expedition() -> str:
    """Get the example unified expedition configuration file."""
    return load_static_file(EXPEDITION)


def _dump_yaml(model: BaseModel, stream: TextIO) -> str | None:
    """Dump a pydantic model to a yaml string."""
    return yaml.safe_dump(
        model.model_dump(by_alias=True), stream, default_flow_style=False
    )


def _generic_load_yaml(data: str, model: BaseModel) -> BaseModel:
    """Load a yaml string into a pydantic model."""
    return model.model_validate(yaml.safe_load(data))


def load_coordinates(file_path):
    """Loads coordinates from a file based on its extension."""
    if not os.path.isfile(file_path):
        raise FileNotFoundError(f"File not found: {file_path}")

    ext = os.path.splitext(file_path)[-1].lower()

    try:
        if ext in [".xls", ".xlsx"]:
            return pd.read_excel(file_path)

        if ext == ".csv":
            return pd.read_csv(file_path)

        raise ValueError(f"Unsupported file extension {ext}.")

    except Exception as e:
        raise RuntimeError(
            "Could not read coordinates data from the provided file. "
            "Ensure it is either a csv or excel file."
        ) from e


def validate_coordinates(coordinates_data):
    # Expected column headers
    expected_columns = {"Station Type", "Name", "Latitude", "Longitude"}

    # Check if the headers match the expected ones
    actual_columns = set(coordinates_data.columns)

    missing_columns = expected_columns - actual_columns
    if missing_columns:
        raise ValueError(
            f"Error: Found columns {list(actual_columns)}, but expected columns {list(expected_columns)}. "
            "Are you sure that you're using the correct export from MFP?"
        )

    extra_columns = actual_columns - expected_columns
    if extra_columns:
        warnings.warn(
            f"Found additional unexpected columns {list(extra_columns)}. "
            "Manually added columns have no effect. "
            "If the MFP export format changed, please submit an issue: "
            "https://github.com/OceanParcels/virtualship/issues.",
            stacklevel=2,
        )

    # Drop unexpected columns (optional, only if you want to ensure strict conformity)
    coordinates_data = coordinates_data[list(expected_columns)]

    # Continue with the rest of the function after validation...
    coordinates_data = coordinates_data.dropna()

    # Convert latitude and longitude to floats, replacing commas with dots
    # Handles case when the latitude and longitude have decimals with commas
    if coordinates_data["Latitude"].dtype in ["object", "string"]:
        coordinates_data["Latitude"] = coordinates_data["Latitude"].apply(
            lambda x: float(x.replace(",", "."))
        )

    if coordinates_data["Longitude"].dtype in ["object", "string"]:
        coordinates_data["Longitude"] = coordinates_data["Longitude"].apply(
            lambda x: float(x.replace(",", "."))
        )

    return coordinates_data


def mfp_to_yaml(coordinates_file_path: str, yaml_output_path: str):  # noqa: D417
    """
    Generates an expedition.yaml file with spatial and temporal information based on instrument data from MFP excel file. Ship config portion of the YAML file is sourced from static version.

    Parameters
    ----------
    - excel_file_path (str): Path to the Excel file containing coordinate and instrument data.

    The function:
    1. Reads instrument and location data from the Excel file.
    2. Determines the maximum depth and buffer based on the instruments present.
    3. Ensures longitude and latitude values remain valid after applying buffer adjustments.
    4. returns the yaml information.

    """
    # avoid circular imports
    from virtualship.models import (
        Expedition,
        Location,
        Schedule,
        ShipConfig,
        SpaceTimeRegion,
        SpatialRange,
        TimeRange,
        Waypoint,
    )

    # Read data from file
    coordinates_data = load_coordinates(coordinates_file_path)

    coordinates_data = validate_coordinates(coordinates_data)

    # maximum depth (in meters), buffer (in degrees) for each instrument
    instrument_max_depths = {
        "XBT": 2000,
        "CTD": 5000,
        "CTD_BGC": 5000,
        "DRIFTER": 1,
        "ARGO_FLOAT": 2000,
    }

    spatial_range = SpatialRange(
        minimum_longitude=coordinates_data["Longitude"].min(),
        maximum_longitude=coordinates_data["Longitude"].max(),
        minimum_latitude=coordinates_data["Latitude"].min(),
        maximum_latitude=coordinates_data["Latitude"].max(),
        minimum_depth=0,
        maximum_depth=max(instrument_max_depths.values()),
    )

    # Create space-time region object
    space_time_region = SpaceTimeRegion(
        spatial_range=spatial_range,
        time_range=TimeRange(),
    )

    # Generate waypoints
    waypoints = []
    for _, row in coordinates_data.iterrows():
        waypoints.append(
            Waypoint(
                instrument=None,  # instruments blank, to be built by user using `virtualship plan` UI or by interacting directly with YAML files
                location=Location(latitude=row["Latitude"], longitude=row["Longitude"]),
            )
        )

    # Create Schedule object
    schedule = Schedule(
        waypoints=waypoints,
        space_time_region=space_time_region,
    )

    # extract ship config object from static
    config = ShipConfig.model_validate(
        yaml.safe_load(get_example_expedition()).get("ship_config")
    )

    # combine to Expedition object
    expedition = Expedition(schedule=schedule, ship_config=config)

    # Save to YAML file
    expedition.to_yaml(yaml_output_path)


def _validate_numeric_mins_to_timedelta(value: int | float | timedelta) -> timedelta:
    """Convert minutes to timedelta when reading."""
    if isinstance(value, timedelta):
        return value
    return timedelta(minutes=value)


def _get_expedition(expedition_dir: Path) -> Expedition:
    """Load Expedition object from yaml config file in `expedition_dir`."""
    from virtualship.models import Expedition

    file_path = expedition_dir.joinpath(EXPEDITION)
    try:
        return Expedition.from_yaml(file_path)
    except FileNotFoundError as e:
        raise FileNotFoundError(
            f'{EXPEDITION} not found. Save it to "{file_path}".'
        ) from e


# custom ship spinner
ship_spinner = Spinner(
    interval=240,
    frames=[
        " 🚢    ",
        "  🚢   ",
        "   🚢  ",
        "    🚢 ",
        "     🚢",
        "    🚢 ",
        "   🚢  ",
        "  🚢   ",
        " 🚢    ",
        "🚢     ",
    ],
)
