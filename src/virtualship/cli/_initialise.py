import os
import warnings
from datetime import timedelta
from functools import lru_cache
from importlib.resources import files
from pathlib import Path

import click
import pandas as pd
import yaml

from virtualship.utils import (
    EXPEDITION,
)


def _initialise(
    path: str | Path, from_mfp: str | None = None, start_date: str | None = None
):
    path = Path(path)
    path.mkdir(exist_ok=True)

    expedition = path / EXPEDITION

    if expedition.exists():
        raise FileExistsError(
            f"File '{expedition}' already exist. Please remove it or choose another directory."
        )

    if from_mfp:
        mfp_file = Path(from_mfp)
        # Generate expedition.yaml from the MPF file
        click.echo(f"Generating schedule from {mfp_file}...")
        _mfp_to_yaml(mfp_file, start_date, expedition)
        # TODO: need to check this interacts as expected with the 'problems' module
        # TODO: and new components need to be added to the 'plan' module to allow users to add ports and instruments to the schedule (keep in waypoints section but without instruments)
        # TODO: but add and remove waypoint buttons should ignore ports
        # TODO: update relevant docs
        #! TODO: `virtualship init` methods are becoming long and complex. Consider refactoring into a separate module for clarity and maintainability (in `virtualship/cli/_init.py`).
        # though, consider confusion of having both `_init.py` and `init.py` in the same directory. Maybe `_init.py` should be renamed to `_init_command.py` or similar.
        # TODO: add a check to see if any instruments are added to a port waypoint (shouldn't be possible via MFP export but in case someone manually edits the expedition.yaml to add instruments to a port waypoint). If so, raise an error and ask user to remove them.
        #! TODO: see utils.py: propagate the warnings to to the user via the click.echo() output in the `virtualship init` command, so that the user sees clearly it in the terminal. Perhaps a warnings section at the bottom.

        click.echo(
            "\n⚠️  The generated schedule does not contain INSTRUMENT selections.  ⚠️"
            "\n\nNow please either use the `\033[4mvirtualship plan\033[0m` app to complete the configuration, "
            "\nOR edit 'expedition.yaml' and manually add the instrument selections under the 'schedule' heading."
            "\n\nIf editing 'expedition.yaml' manually:"
            "\n\n🌡️   Expected instrument(s) format: one line per instrument e.g."
            f"\n\n{' ' * 15}waypoints:\n{' ' * 15}- instrument:\n{' ' * 19}- CTD\n{' ' * 19}- ARGO_FLOAT\n"
        )
    else:
        # Create a default example expedition YAML
        expedition.write_text(_get_example_expedition())

    click.echo(f"Created '{expedition.name}' at {path}.")


def _mfp_to_yaml(file_path: str, start_date: str, output_path: str):
    """Generates an expedition.yaml file with schedule information based on data from MFP excel file. The ship and instrument configurations entries in the YAML file are sourced from the static version."""
    # avoid circular imports
    from virtualship.models import (
        Expedition,
        InstrumentsConfig,
        Location,
        Port,
        Schedule,
        Waypoint,
    )

    # Read data from file
    mfp_data = _validate_mfp_data(file_path)

    # Generate ports/waypoints
    waypoints = []
    current_time, previous_timedelta = start_date, None
    for i, row in mfp_data.iterrows():
        if i > 0:
            current_time += previous_timedelta
        is_port = "Port" in row["Station"] or "Port" in row["Type"]

        if is_port:
            has_latlon = not pd.isna(row["Latitude"]) and not pd.isna(
                row["Longitude"]
            )  # indicates that the port has been set in MFP / is not a placeholder

            waypoints.append(
                Port(
                    location=Location(
                        latitude=row["Latitude"], longitude=row["Longitude"]
                    ),
                    time=current_time if has_latlon else None,
                )
            )
        else:
            waypoints.append(
                Waypoint(
                    instrument=None,
                    location=Location(
                        latitude=row["Latitude"], longitude=row["Longitude"]
                    ),
                    time=current_time,
                )
            )

        # store total timedelta for next iteration
        previous_timedelta = (
            row["Total Time"] if row["Total Time"] is not pd.NaT else timedelta(0)
        )

    # Create Schedule object
    schedule = Schedule(
        waypoints=waypoints,
    )

    # extract instruments config from static
    instruments_config = InstrumentsConfig.model_validate(
        yaml.safe_load(_get_example_expedition()).get("instruments_config")
    )

    # extract ship config from static
    ship_config = yaml.safe_load(_get_example_expedition()).get("ship_config")
    # combine to Expedition object
    expedition = Expedition(
        schedule=schedule,
        instruments_config=instruments_config,
        ship_config=ship_config,
    )

    # Save to YAML file
    expedition.to_yaml(output_path)


def _validate_mfp_data(file_path):
    """Load and validate MFP CruiseData export."""
    errmsg_supplement = "If the MFP export format has changed, please submit an issue at: https://github.com/Parcels-code/virtualship/issues."

    mfp_data = _load_mfp_export(file_path)

    # clean up column names
    mfp_data.columns = mfp_data.columns.astype(str).str.strip()
    mfp_data = mfp_data.loc[
        :, ~mfp_data.columns.str.startswith("Unnamed") & (mfp_data.columns != "")
    ]

    expected_columns = {
        "Station",
        "Type",
        "Latitude",
        "Longitude",
        "Sea Depth",
        "Time at Station",
        "Travel Time to Next",
        "Distance to Next (NM)",
        "Ship Speed (kn)",
        "EEZ",
    }

    actual_columns = set(mfp_data.columns)

    missing_columns = expected_columns - actual_columns
    if missing_columns:
        raise ValueError(
            f"Error: Found columns {list(actual_columns)}, but expected columns {list(expected_columns)}. "
            "Are you sure that you're using the correct export from MFP?\n\n"
            + errmsg_supplement
        )

    extra_columns = actual_columns - expected_columns
    if extra_columns:
        # TODO: as mentioned below, propagate this warning to the user via the click.echo() output in the `virtualship init` command?
        warnings.warn(
            f"Found additional unexpected columns {list(extra_columns)}. "
            "Manually added columns have no effect. " + errmsg_supplement,
            stacklevel=2,
        )

    # Convert latitude and longitude to floats, handling commas and missing values safely
    for coord in ["Latitude", "Longitude"]:
        if mfp_data[coord].dtype in ["object", "string"]:
            mfp_data[coord] = pd.to_numeric(
                mfp_data[coord].astype(str).str.replace(",", "."), errors="coerce"
            )

    # check for missing departure/arrival ports and add placeholders if necessary
    # check against both 'Station' and 'Type' columns; variations can occur when importing to MFP before re-exporting
    has_departure = (
        "Departure Port" in mfp_data["Station"].values
        or "Departure Port" in mfp_data["Type"].values
    )
    has_arrival = (
        "Arrival Port" in mfp_data["Station"].values
        or "Arrival Port" in mfp_data["Type"].values
    )
    if not has_departure or not has_arrival:
        # TODO: propagate the warning to to the user via the click.echo() output in the `virtualship init` command, so that the user sees clearly it in the terminal. Perhaps a warnings section at the bottom.
        warnings.warn(
            "The MFP export is missing either a 'Departure Port' or 'Arrival Port', or both. "
            "Any missing port will be replaced with a placeholder in `expedition.yaml` but will be ignored in the simulation. "
            "The prescribed date will be used for Waypoint #1 instead. "
            "If you believe this warning is wrong (i.e. you have selected departure/arrival ports), and "
            + errmsg_supplement.replace("If ", ""),
            stacklevel=2,
        )

        if not has_departure:
            dept_row = _create_port_row(expected_columns, "Departure Port")
            mfp_data = pd.concat([dept_row, mfp_data], ignore_index=True)  # first row

        if not has_arrival:
            arr_row = _create_port_row(expected_columns, "Arrival Port")
            mfp_data = pd.concat([mfp_data, arr_row], ignore_index=True)  # last row

    # Drop unexpected columns
    mfp_data = mfp_data[list(expected_columns)]

    # convert 'Travel Time to Next' and 'Time at Station' to timedelta
    mfp_data["Travel Time to Next"] = mfp_data["Travel Time to Next"].apply(
        lambda x: _mfp_string_to_timedelta(x)
    )
    mfp_data["Time at Station"] = mfp_data["Time at Station"].apply(
        lambda x: _mfp_string_to_timedelta(x)
    )

    # combine 'Travel Time to Next' and 'Time at Station' into a single 'Total Time' column
    # add 0 when Time at Station is NaN, to avoid NaT in Total Time, but not to Travel Time to keep NaT at the arrival port
    mfp_data["Total Time"] = mfp_data["Travel Time to Next"] + mfp_data[
        "Time at Station"
    ].fillna(pd.Timedelta(0))

    return mfp_data


def _load_mfp_export(file_path):
    if not os.path.isfile(file_path):
        raise FileNotFoundError(f"File not found: {file_path}")

    try:
        df = pd.read_excel(file_path)
        return df.dropna(how="all", axis=1)  # drop empty columns

    except Exception as e:
        raise RuntimeError(
            "Could not read coordinates data from the provided file. "
            "Ensure it is an exported .xlsx file from MFP."
        ) from e


def _create_port_row(columns, port_type):
    """Generate a single placeholder row for missing departure/arrival ports."""
    row = {col: None for col in columns}
    row["Station"] = port_type
    row["Type"] = port_type
    return pd.DataFrame([row])


def _mfp_string_to_timedelta(value: str) -> timedelta:
    """Handle MFP export string format (e.g., "0d 13h 13m")."""
    if pd.isna(value):  # last waypoint/missing ports have NaN/None travel time
        return value  # return None

    value = value.replace("d", ":").replace("h", ":").replace("m", "")
    days, hours, minutes = map(int, value.split(":"))
    return timedelta(days=days, hours=hours, minutes=minutes)


def _load_static_file(name: str) -> str:
    """Load static file from the ``virtualship.static`` module by file name."""
    return files("virtualship.static").joinpath(name).read_text(encoding="utf-8")


@lru_cache(None)
@lru_cache(None)
def _get_example_expedition() -> str:
    """Get the example unified expedition configuration file."""
    return _load_static_file(EXPEDITION)


def _validate_start_date(ctx, param, value):
    """Callback to enforce and validate --start-date when --from-mfp is used."""
    if ctx.params.get("from_mfp"):
        if not value:
            raise click.BadParameter(
                "The '--start-date' option is required when using '--from-mfp'."
                "\n\nExpected format: 'YYYY-MM-DD HH:MM:SS' (with quotes, e.g., '2023-10-20 01:00:00'). If only the date is provided, the time will default to 00:00:00."
            )
    return value
