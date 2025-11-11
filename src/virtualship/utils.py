from __future__ import annotations

import os
import warnings
from datetime import timedelta
from functools import lru_cache
from importlib.resources import files
from pathlib import Path
from typing import TYPE_CHECKING, TextIO

import copernicusmarine
import numpy as np
import xarray as xr
from parcels import FieldSet

from virtualship.errors import CopernicusCatalogueError

if TYPE_CHECKING:
    from virtualship.expedition.simulate_schedule import ScheduleOk
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
    Generates an expedition.yaml file with schedule information based on data from MFP excel file. The ship and instrument configurations entries in the YAML file are sourced from the static version.

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
        InstrumentsConfig,
        Location,
        Schedule,
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

    # extract instruments config from static
    instruments_config = InstrumentsConfig.model_validate(
        yaml.safe_load(get_example_expedition()).get("instruments_config")
    )

    # extract ship config from static
    ship_config = yaml.safe_load(get_example_expedition()).get("ship_config")

    # combine to Expedition object
    expedition = Expedition(
        schedule=schedule,
        instruments_config=instruments_config,
        ship_config=ship_config,
    )

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


# InstrumentType -> Instrument registry and registration utilities.
INSTRUMENT_CLASS_MAP = {}


def register_instrument(instrument_type):
    def decorator(cls):
        INSTRUMENT_CLASS_MAP[instrument_type] = cls
        return cls

    return decorator


def get_instrument_class(instrument_type):
    return INSTRUMENT_CLASS_MAP.get(instrument_type)


def add_dummy_UV(fieldset: FieldSet):
    """Add a dummy U and V field to a FieldSet to satisfy parcels FieldSet completeness checks."""
    if "U" not in fieldset.__dict__.keys():
        for uv_var in ["U", "V"]:
            dummy_field = getattr(
                FieldSet.from_data(
                    {"U": 0, "V": 0}, {"lon": 0, "lat": 0}, mesh="spherical"
                ),
                uv_var,
            )
            fieldset.add_field(dummy_field)
            try:
                fieldset.time_origin = (
                    fieldset.T.grid.time_origin
                    if "T" in fieldset.__dict__.keys()
                    else fieldset.o2.grid.time_origin
                )
            except Exception:
                raise ValueError(
                    "Cannot determine time_origin for dummy UV fields. Assert T or o2 exists in fieldset."
                ) from None


# Copernicus Marine product IDs

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

# variables used in VirtualShip which are physical or biogeochemical variables, respectively
COPERNICUSMARINE_PHYS_VARIABLES = ["uo", "vo", "so", "thetao"]
COPERNICUSMARINE_BGC_VARIABLES = ["o2", "chl", "no3", "po4", "ph", "phyc", "nppv"]


def _select_product_id(
    physical: bool,
    schedule_start,
    schedule_end,
    username: str | None = None,
    password: str | None = None,
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
        ds = copernicusmarine.open_dataset(pid, username=username, password=password)
        time_end = ds["time"][-1].values
        if np.datetime64(schedule_end) <= time_end:
            selected_id = pid
            break

    if selected_id is None:
        raise CopernicusCatalogueError(
            "No suitable product found in the Copernicus Marine Catalogue for the scheduled time and variable."
        )

    if _start_end_in_product_timerange(
        selected_id, schedule_start, schedule_end, username, password
    ):
        return selected_id
    else:
        return (
            PRODUCT_IDS["phys"]["analysis"] if physical else BGC_ANALYSIS_IDS[variable]
        )


def _start_end_in_product_timerange(
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


def _get_bathy_data(
    space_time_region, latlon_buffer: float | None = None, from_data: Path | None = None
) -> FieldSet:
    """Bathymetry data from local or 'streamed' directly from Copernicus Marine."""
    if from_data is not None:  # load from local data
        var = "deptho"
        try:
            filename, _ = _find_nc_file_with_variable(from_data, var)
        except Exception as e:
            raise RuntimeError(
                f"Could not find bathymetry variable '{var}' in provided data directory '{from_data}'."
            ) from e
        ds_bathymetry = xr.open_dataset(from_data.joinpath(filename))
        bathymetry_variables = {"bathymetry": "deptho"}
        bathymetry_dimensions = {"lon": "longitude", "lat": "latitude"}
        return FieldSet.from_xarray_dataset(
            ds_bathymetry, bathymetry_variables, bathymetry_dimensions
        )

    else:  # stream via Copernicus Marine
        ds_bathymetry = copernicusmarine.open_dataset(
            dataset_id="cmems_mod_glo_phy_my_0.083deg_static",
            minimum_longitude=space_time_region.spatial_range.minimum_longitude
            - (latlon_buffer if latlon_buffer is not None else 0),
            maximum_longitude=space_time_region.spatial_range.maximum_longitude
            + (latlon_buffer if latlon_buffer is not None else 0),
            minimum_latitude=space_time_region.spatial_range.minimum_latitude
            - (latlon_buffer if latlon_buffer is not None else 0),
            maximum_latitude=space_time_region.spatial_range.maximum_latitude
            + (latlon_buffer if latlon_buffer is not None else 0),
            variables=["deptho"],
            start_datetime=space_time_region.time_range.start_time,
            end_datetime=space_time_region.time_range.end_time,
            coordinates_selection_method="outside",
        )
        bathymetry_variables = {"bathymetry": "deptho"}
        bathymetry_dimensions = {"lon": "longitude", "lat": "latitude"}

    return FieldSet.from_xarray_dataset(
        ds_bathymetry, bathymetry_variables, bathymetry_dimensions
    )


def expedition_cost(schedule_results: ScheduleOk, time_past: timedelta) -> float:
    """
    Calculate the cost of the expedition in US$.

    :param schedule_results: Results from schedule simulation.
    :param time_past: Time the expedition took.
    :returns: The calculated cost of the expedition in US$.
    """
    SHIP_COST_PER_DAY = 30000
    DRIFTER_DEPLOY_COST = 2500
    ARGO_DEPLOY_COST = 15000

    ship_cost = SHIP_COST_PER_DAY / 24 * time_past.total_seconds() // 3600
    num_argos = len(schedule_results.measurements_to_simulate.argo_floats)
    argo_cost = num_argos * ARGO_DEPLOY_COST
    num_drifters = len(schedule_results.measurements_to_simulate.drifters)
    drifter_cost = num_drifters * DRIFTER_DEPLOY_COST

    cost = ship_cost + argo_cost + drifter_cost
    return cost


def _find_nc_file_with_variable(data_dir: Path, var: str) -> str | None:
    """Search for a .nc file in the given directory containing the specified variable."""
    for nc_file in data_dir.glob("*.nc"):
        try:
            with xr.open_dataset(nc_file, chunks={}) as ds:
                matched_vars = [v for v in ds.variables if var in v]
                if matched_vars:
                    return nc_file.name, matched_vars[0]
        except Exception:
            continue
    return None
