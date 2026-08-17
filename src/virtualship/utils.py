from __future__ import annotations

import glob
import hashlib
import re
from datetime import datetime, timedelta
from pathlib import Path
from typing import TYPE_CHECKING, Literal, TextIO

import copernicusmarine
import numpy as np
import parcels
import pyproj
import xarray as xr
from parcels import FieldSet, Particle, Variable

from virtualship.errors import CopernicusCatalogueError
from virtualship.models.expedition import Port

if TYPE_CHECKING:
    from virtualship.expedition.simulate_schedule import (
        ScheduleOk,
    )
    from virtualship.models import Expedition, InstrumentsConfig, Location
    from virtualship.models.checkpoint import Checkpoint
    from virtualship.models.expedition import SensorConfig

import yaml
from pydantic import BaseModel
from yaspin import Spinner

# =====================================================
# SECTION: simulation constants
# =====================================================

EXPEDITION = "expedition.yaml"
CHECKPOINT = "checkpoint.yaml"
RESULTS = "results"

# projection used to sail between waypoints
PROJECTION = pyproj.Geod(ellps="WGS84")

# caching for problems module
CACHE = "cache"
EXPEDITION_IDENTIFIER = "id_latest.txt"
PROBLEMS_ENCOUNTERED = "problems_encountered_" + "{expedition_id}"
SELECTED_PROBLEMS = "selected_problems.json"
REPORT = "post_expedition_report.txt"

EXPEDITION_ORIGINAL = "expedition_original.yaml"
EXPEDITION_LATEST = "expedition_latest.yaml"


# =====================================================
# SECTION: Copernicus Marine Service constants
# =====================================================

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

BATHYMETRY_ID = "cmems_mod_glo_phy_my_0.083deg_static"


# =====================================================
# SECTION: decorators / dynamic registries and mapping
# =====================================================

# helpful for dynamic access in different parts of the codebase

# main instrument (simulation) class registry and registration utilities
INSTRUMENT_CLASS_MAP = {}

# maps InstrumentType to frozenset[SensorType], to set which sensors each instrument suppors, auto-populated by @register_instrument
SUPPORTED_SENSORS_MAP: dict = {}


def register_instrument(instrument_type):
    def decorator(cls):
        INSTRUMENT_CLASS_MAP[instrument_type] = cls
        if hasattr(cls, "sensor_kernels"):  # derive supported kernels from class attr
            SUPPORTED_SENSORS_MAP[instrument_type] = frozenset(
                cls.sensor_kernels.keys()
            )
        return cls

    return decorator


def get_instrument_class(instrument_type):
    return INSTRUMENT_CLASS_MAP.get(instrument_type)


def get_supported_sensors(instrument_type):
    """Return the frozenset of SensorTypes supported by the given InstrumentType."""
    supported = SUPPORTED_SENSORS_MAP.get(instrument_type)
    if supported is None:
        raise KeyError(
            f"No supported sensors registered for {instrument_type!r}. "
            f"Does the instrument class define a `sensor_kernels` attribute?"
        )
    return supported


# map for instrument type to instrument config (pydantic basemodel) names
INSTRUMENT_CONFIG_MAP = {}


def register_instrument_config(instrument_type):
    def decorator(cls):
        INSTRUMENT_CONFIG_MAP[instrument_type] = cls.__name__
        return cls

    return decorator


# =====================================================
# SECTION: helper functions
# =====================================================


def _dump_yaml(model: BaseModel, stream: TextIO) -> str | None:
    """Dump a pydantic model to a yaml string."""
    return yaml.safe_dump(
        model.model_dump(by_alias=True), stream, default_flow_style=False
    )


def _generic_load_yaml(data: str, model: BaseModel) -> BaseModel:
    """Load a yaml string into a pydantic model."""
    return model.model_validate(yaml.safe_load(data))


def _validate_numeric_to_timedelta(
    value: int | float | timedelta, unit: Literal["minutes", "days"]
) -> timedelta:
    """Convert to timedelta when reading."""
    if isinstance(value, timedelta):
        return value
    if unit == "minutes":
        return timedelta(minutes=float(value))
    elif unit == "days":
        return timedelta(days=float(value))
    else:
        raise ValueError(
            f"Unsupported time unit: {unit}. Supported units are: 'minutes', 'days'."
        )


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


def _get_bathy_data(from_data: Path | None = None) -> FieldSet:
    """Bathymetry data from local or 'streamed' directly from Copernicus Marine."""
    VAR = "deptho"
    if from_data is not None:  # load from local data
        bathy_dir = from_data.joinpath("bathymetry")
        try:
            filename, _ = _find_nc_file_with_variable(bathy_dir, VAR)
        except Exception as e:
            raise RuntimeError(
                f"\n\n❗️ Could not find bathymetry variable '{VAR}' in data directory '{from_data}/bathymetry/'.\n\n❗️ Is the pre-downloaded data directory structure compliant with VirtualShip expectations?\n\n❗️ See the docs for more information on expectations: https://virtualship.readthedocs.io/en/latest/user-guide/index.html#documentation\n"
            ) from e
        ds_bathymetry = xr.open_dataset(bathy_dir.joinpath(filename))

    else:  # stream via Copernicus Marine Service
        ds_bathymetry = copernicusmarine.open_dataset(
            dataset_id=BATHYMETRY_ID,
            variables=[VAR],
            coordinates_selection_method="outside",
        )

    # give a depth dimension and make bathymetry negative
    ds_bathymetry = ds_bathymetry.expand_dims({"depth": 1})
    ds_bathymetry[VAR] = -ds_bathymetry[VAR]

    ds_fset = parcels.convert.copernicusmarine_to_sgrid(
        fields={"bathymetry": ds_bathymetry[VAR]}
    )

    return FieldSet.from_sgrid_conventions(ds_fset)


def expedition_cost(schedule_results: ScheduleOk, time_past: timedelta) -> float:
    """
    Calculate the cost of the expedition in US$.

    :param schedule_results: Results from schedule simulation.
    :param time_past: Time the expedition took.
    :returns: The calculated cost of the expedition in US$.
    """
    # TODO: refactor to instrument sub-classes attributes...?
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
            with xr.open_dataset(nc_file) as ds:
                matched_vars = [v for v in ds.variables if var in v]
                if matched_vars:
                    return nc_file.name, matched_vars[0]
        except Exception:
            continue
    return None


def _find_files_in_timerange(
    data_dir: Path,
    schedule_start,
    schedule_end,
    date_pattern=r"\d{4}_\d{2}_\d{2}",
    date_fmt="%Y_%m_%d",
) -> list:
    """Find all files in data_dir whose filenames contain a date within [schedule_start, schedule_end] (inclusive)."""
    # TODO: scope to make this more flexible for different date patterns / formats ... ?

    all_files = glob.glob(str(data_dir.joinpath("*")))
    if not all_files:
        raise ValueError(
            f"No files found in data directory {data_dir}. Please ensure the directory contains files with 'P1D' or 'P1M' in their names as per Copernicus Marine Product ID naming conventions."
        )

    if all("P1D" in s for s in all_files):
        t_resolution = "daily"
    elif all("P1M" in s for s in all_files):
        t_resolution = "monthly"
    else:
        raise ValueError(
            f"Could not determine time resolution from filenames in data directory. Please ensure all filenames in {data_dir} contain either 'P1D' (daily) or 'P1M' (monthly), "
            f"as per the Copernicus Marine Product ID naming conventions."
        )

    if t_resolution == "monthly":
        t_min = schedule_start.date().replace(
            day=1
        )  # first day of month of the schedule start date
        t_max = (
            schedule_end.date()
            + timedelta(
                days=32
            )  # buffer to ensure fieldset end date is always longer than schedule end date for monthly data
        )
    else:  # daily
        t_min = schedule_start.date()
        t_max = schedule_end.date()

    files_with_dates = []
    for file in data_dir.iterdir():
        if file.is_file():
            match = re.search(date_pattern, file.name)
            if match:
                file_date = datetime.strptime(
                    match.group(), date_fmt
                ).date()  # normalise to date only for comparison (given start/end dates have hour/minute components which may exceed those in file_date)
                if t_min <= file_date <= t_max:
                    files_with_dates.append((file_date, file.name))

    files_with_dates.sort(
        key=lambda x: x[0]
    )  # sort by extracted date; more robust than relying on filesystem order

    # catch if not enough data coverage found for the requested time range
    if files_with_dates[-1][0] < schedule_end.date():
        raise ValueError(
            f"Not enough data coverage found in {data_dir} for the requested time range {schedule_start} to {schedule_end}. "
            f"Latest available data is for date {files_with_dates[-1][0]}."
            f"If using monthly data, please ensure that the last month downloaded covers the schedule end date + 1 month."
            f"See the docs for more details: https://virtualship.readthedocs.io/en/latest/user-guide/index.html#documentation"
        )

    return [fname for _, fname in files_with_dates]


def _compute_max_depths(measurements, fieldset) -> list[float]:
    """Compute the effective max depth for each measurement, capped by bathymetry."""
    return [
        max(
            m.max_depth,
            fieldset.bathymetry.eval(
                z=0,
                y=m.spacetime.location.lat,
                x=m.spacetime.location.lon,
                t=np.float64(0),
            )[0],
        )
        for m in measurements
    ]


def _random_noise(scale: float = 0.05, limit: float = 0.1) -> float:
    """Generate a small random noise value for drifter seeding locations."""
    value = np.random.normal(loc=0.0, scale=scale)
    return np.clip(value, -limit, limit)  # ensure noise is within limits


def _get_waypoint_latlons(waypoints):
    """Extract latitudes and longitudes from waypoints."""
    wp_lats, wp_lons = zip(
        *[(wp.location.latitude, wp.location.longitude) for wp in waypoints],
        strict=True,
    )
    return wp_lats, wp_lons


def _save_checkpoint(checkpoint: Checkpoint, expedition_dir: Path) -> None:
    file_path = expedition_dir.joinpath(CHECKPOINT)
    checkpoint.to_yaml(file_path)


def _calc_sail_time(
    location1: Location,
    location2: Location,
    ship_speed_knots: float,
    projection: pyproj.Geod,
) -> tuple[timedelta, tuple[float, float, float], float]:
    """Calculate sail time between two waypoints (their locations) given ship speed in knots."""
    geodinv: tuple[float, float, float] = projection.inv(
        lons1=location1.longitude,
        lats1=location1.latitude,
        lons2=location2.longitude,
        lats2=location2.latitude,
    )
    ship_speed_meter_per_second = ship_speed_knots * 1852 / 3600
    distance_to_next_waypoint = geodinv[2]
    return (
        timedelta(seconds=distance_to_next_waypoint / ship_speed_meter_per_second),
        geodinv[0],
        ship_speed_meter_per_second,
    )


def _calc_wp_stationkeeping_time(
    wp_instrument_types: list | None,
    instruments_config: InstrumentsConfig,
    instrument_config_map: dict = INSTRUMENT_CONFIG_MAP,
) -> timedelta:
    """For a given waypoint (and the instruments present at this waypoint), calculate how much time is required to carry out all instrument deployments."""
    # to empty list if wp instruments set to 'null'
    if not wp_instrument_types:
        wp_instrument_types = []

    # extract configs for all instruments present in expedition
    valid_instrument_configs = [
        iconfig for _, iconfig in instruments_config.__dict__.items() if iconfig
    ]

    # extract configs for instruments present in given waypoint
    wp_instrument_configs = []
    for iconfig in valid_instrument_configs:
        for itype in wp_instrument_types:
            if (
                instrument_config_map.get(itype) == iconfig.__class__.__name__
                and (
                    iconfig not in wp_instrument_configs
                )  # avoid duplicates (would happen when multiple drifter deployments at same waypoint)
            ):
                wp_instrument_configs.append(iconfig)

    # get wp total stationkeeping time
    cumulative_stationkeeping_time = timedelta()
    for iconfig in wp_instrument_configs:
        if hasattr(iconfig, "stationkeeping_time"):
            cumulative_stationkeeping_time += iconfig.stationkeeping_time

    return cumulative_stationkeeping_time


def _make_hash(s: str, length: int) -> str:
    """Make unique hash for problem occurrence."""
    assert length % 2 == 0, "Length must be even."
    half_length = length // 2
    return hashlib.shake_128(s.encode("utf-8")).hexdigest(half_length)


def build_particle_class_from_sensors(
    sensors: list[SensorConfig],
    nonsensor_variables: list[Variable],
) -> type:
    """Build a Particle class from nonsensor variables and active sensors."""
    sensor_variables = [
        variable for sc in sensors if sc.enabled for variable in sc.meta.particle_vars
    ]

    return Particle.add_variable(nonsensor_variables + sensor_variables)


def _get_clean_encoding(ds):
    """
    Clean existing encodings and supply explicit native endianness to prevent netCDF4 UserWarnings.

    Helps avoid annoying user warnings when writing tmp files to disk.
    """
    encoding = {}
    for var_name, var in ds.variables.items():
        var.encoding.pop("endian", None)
        encoding[var_name] = {"endian": "native"}

    return encoding


def _get_public_wp(raw_wp_i: int | None, waypoints: list) -> int | None:
    """Get the public waypoint index for a given waypoint (accounting for Port waypoints)."""
    non_port_wps = [i for i, wp in enumerate(waypoints) if not isinstance(wp, Port)]
    return non_port_wps.index(raw_wp_i) + 1 if raw_wp_i is not None else None


# =====================================================
# SECTION: misc.
# =====================================================


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
