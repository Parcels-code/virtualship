import os
import re
import warnings
from datetime import timedelta
from pathlib import Path

import click
import pandas as pd
import yaml

from virtualship.models import (
    Expedition,
    InstrumentsConfig,
    Location,
    Port,
    Schedule,
    Waypoint,
)
from virtualship.utils import EXPEDITION, _get_example_expedition

ERR_SUPPLEMENT = "If the MFP export format has changed, please submit an issue at: https://github.com/Parcels-code/virtualship/issues."


def _initialise(
    path: str | Path, from_mfp: str | None = None, start_date: str | None = None
):
    path = Path(path)
    path.mkdir(exist_ok=True)

    expedition = path / EXPEDITION

    if expedition.exists():
        raise FileExistsError(
            f"File '{expedition}' already exists. Please remove it or use another directory."
        )

    if from_mfp:
        mfp_file = Path(from_mfp)
        click.echo(f"Generating schedule from {mfp_file}...")

        # catch warnings raised to propagate them via click.echo
        with warnings.catch_warnings(record=True) as captured_warnings:
            warnings.simplefilter("always")
            _mfp_to_yaml(mfp_file, start_date, expedition)

        indent = " " * 4
        click.echo(
            "\n⚠️  The generated schedule does not contain INSTRUMENT selections.  ⚠️"
            "\n\nNow please either use the `\033[4mvirtualship plan\033[0m` app to complete the configuration, "
            "\nOR edit 'expedition.yaml' and manually add the instrument selections under the 'schedule' heading."
            "\n\nIf editing 'expedition.yaml' manually:"
            "\n\n🌡️  Expected instrument(s) format: one line per instrument e.g."
            f"\n\n{indent * 4}waypoints:\n{indent * 4}- instrument:\n{indent * 5}- CTD\n{indent * 5}- ARGO_FLOAT\n"
        )

        # output captured warnings to the terminal
        if captured_warnings:
            click.echo("\n❗️ WARNINGS:")
            for w in captured_warnings:
                click.echo(f"{indent}• {w.message}")
            click.echo(
                f"\n{indent}If you believe any of these warnings are incorrect (e.g. you have selected departure/arrival ports), and {ERR_SUPPLEMENT.replace('If ', '')}\n"
            )
    else:
        expedition.write_text(_get_example_expedition())

    click.echo(f"Created '{expedition.name}' at {path}.")


def _mfp_to_yaml(file_path: Path, start_date: str, output_path: Path):
    """Generates an expedition.yaml file from MFP Excel export."""
    mfp_data = _validate_mfp_data(file_path)

    # convert start_date string to datetime object if needed, ensuring it's standard Python datetime
    if isinstance(start_date, str):
        current_time = pd.to_datetime(start_date).to_pydatetime()
    elif isinstance(start_date, pd.Timestamp):
        current_time = start_date.to_pydatetime()
    else:
        current_time = start_date

    waypoints = []
    previous_timedelta = None

    for i, row in mfp_data.iterrows():
        if i > 0:
            current_time += previous_timedelta

        is_port = "Port" in str(row["Station"]) or "Port" in str(row["Type"])
        lat = None if pd.isna(row["Latitude"]) else float(row["Latitude"])
        lon = None if pd.isna(row["Longitude"]) else float(row["Longitude"])
        loc = Location(latitude=lat, longitude=lon)

        # Ensure timestamp passed is a native python datetime (or string) to prevent PyYAML pandas pickle tags
        time_val = (
            current_time.to_pydatetime()
            if isinstance(current_time, pd.Timestamp)
            else current_time
        )

        if is_port:
            has_latlon = lat is not None and lon is not None
            waypoints.append(Port(location=loc, time=time_val if has_latlon else None))
        else:
            waypoints.append(Waypoint(instrument=None, location=loc, time=time_val))

        previous_timedelta = (
            row["Total Time"] if pd.notna(row["Total Time"]) else timedelta(0)
        )

    # build and dump expedition YAML
    static_yaml = yaml.safe_load(_get_example_expedition())
    expedition = Expedition(
        schedule=Schedule(waypoints=waypoints),
        instruments_config=InstrumentsConfig.model_validate(
            static_yaml.get("instruments_config")
        ),
        ship_config=static_yaml.get("ship_config"),
    )
    expedition.to_yaml(output_path)


def _validate_mfp_data(file_path: Path) -> pd.DataFrame:
    """Load and validate MFP CruiseData export."""
    mfp_data = _load_mfp_export(file_path)

    # clean up column names
    mfp_data.columns = mfp_data.columns.astype(str).str.strip()
    junk_col_pattern = r"^(Unnamed:.*||\.\d+)$"
    mfp_data = mfp_data.loc[:, ~mfp_data.columns.str.match(junk_col_pattern)]

    expected_columns = [
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
    ]
    expected_set = set(expected_columns)
    actual_set = set(mfp_data.columns)

    missing_columns = expected_set - actual_set
    if missing_columns:
        raise ValueError(
            f"Error: Found columns {list(actual_set)}, but expected columns {list(expected_columns)}. "
            f"Are you sure that you're using the correct export from MFP?\n\n{ERR_SUPPLEMENT}"
        )

    extra_columns = actual_set - expected_set
    if extra_columns:
        warnings.warn(
            f"Found additional unexpected columns {list(extra_columns)}. These will be dropped from the export. Manually added columns have no effect.",
            stacklevel=2,
        )

    # drop unexpected columns
    mfp_data = mfp_data[list(expected_columns)]

    # safe float conversion for lat/lon
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
        warnings.warn(
            "The MFP export is missing either a 'Departure Port' or 'Arrival Port', or both. "
            "Any missing port will be replaced with an empty placeholder in `expedition.yaml` but will be ignored in the simulation. "
            "If missing the 'Departure Port', the prescribed start date will be used for Waypoint #1 instead. ",
            stacklevel=2,
        )

        if not has_departure:
            dept_row = _create_port_row(expected_columns, "Departure Port")
            mfp_data = pd.concat([dept_row, mfp_data], ignore_index=True)  # first row

        if not has_arrival:
            arr_row = _create_port_row(expected_columns, "Arrival Port")
            mfp_data = pd.concat([mfp_data, arr_row], ignore_index=True)  # last row

    # convert 'Travel Time to Next' and 'Time at Station' to timedelta
    mfp_data["Travel Time to Next"] = mfp_data["Travel Time to Next"].apply(
        _mfp_string_to_timedelta
    )
    mfp_data["Time at Station"] = mfp_data["Time at Station"].apply(
        _mfp_string_to_timedelta
    )

    # combine 'Travel Time to Next' and 'Time at Station' into a single 'Total Time' column
    # add 0 when Time at Station is NaN, to avoid NaT in Total Time, but not to Travel Time to keep NaT at the arrival port
    mfp_data["Total Time"] = mfp_data["Travel Time to Next"] + mfp_data[
        "Time at Station"
    ].fillna(pd.Timedelta(0))

    return mfp_data


def _load_mfp_export(file_path: Path) -> pd.DataFrame:
    if not os.path.isfile(file_path):
        raise FileNotFoundError(f"File not found: {file_path}")

    try:
        return pd.read_excel(file_path).dropna(how="all", axis=1)  # drop empty columns
    except Exception as e:
        raise RuntimeError(
            "Could not read coordinates data from the provided file. "
            "Ensure it is an exported .xlsx file from MFP."
        ) from e


def _create_port_row(columns, port_type: str) -> pd.DataFrame:
    """Generate a single placeholder row for missing departure/arrival ports."""
    row = {col: None for col in columns}
    row["Station"] = port_type
    row["Type"] = port_type
    return pd.DataFrame([row])


def _mfp_string_to_timedelta(value: str | None) -> timedelta | None:
    """Parse MFP duration string (e.g., '0d 13h 13m') to timedelta."""
    if pd.isna(value):
        return None

    match = re.search(r"(\d+)d\s*(\d+)h\s*(\d+)m", str(value))
    if match:
        days, hours, minutes = map(int, match.groups())
        return timedelta(days=days, hours=hours, minutes=minutes)

    else:
        raise ValueError(
            f"Invalid MFP duration format: '{value}'. Expected format: 'Xd Yh Zm' (e.g., '0d 13h 13m'). {ERR_SUPPLEMENT}"
        )


def _validate_start_date(ctx, param, value):
    """Enforce --start-date when --from-mfp is used."""
    if ctx.params.get("from_mfp"):
        if not value:
            raise click.BadParameter(
                "The '--start-date' option is required when using '--from-mfp'."
                "\n\nExpected format: 'YYYY-MM-DD HH:MM:SS' (with quotes, e.g., '2023-10-20 01:00:00'). If only the date is provided, the time will default to 00:00:00."
            )
    return value
