from pathlib import Path

import click

from virtualship.cli._initialise import _initialise, _validate_start_date
from virtualship.cli._plan import _plan
from virtualship.cli._run import _run
from virtualship.utils import (
    COPERNICUSMARINE_BGC_VARIABLES,
    COPERNICUSMARINE_PHYS_VARIABLES,
)


@click.command()
@click.argument(
    "path",
    type=click.Path(exists=False, file_okay=False, dir_okay=True),
)
@click.option(
    "--from-mfp",
    type=str,
    default=None,
    help="Partially initialise a project from an exported xlsx or csv file from NIOZ' "
    'Marine Facilities Planning tool (specifically the "Export Coordinates > DD" option). '
    "User edits are required after initialisation.",
)
@click.option(
    "--start-date",
    type=click.DateTime(formats=["%Y-%m-%d %H:%M:%S", "%Y-%m-%d"]),
    default=None,
    callback=_validate_start_date,
    help="The departure/start date of the expedition (required when using --from-mfp). "
    "Expected format: 'YYYY-MM-DD HH:MM:SS' (with quotes, e.g., '2023-10-20 01:00:00'). If only the date is provided, the time will default to 00:00:00.",
)
def init(path, from_mfp, start_date):
    """
    Initialize a directory for a new expedition, with an expedition.yaml file.

    If --mfp-file is provided (and --start-date is also provided), it will generate the expedition.yaml from the MPF file instead.
    """
    _initialise(Path(path), from_mfp, start_date)


@click.command()
@click.argument(
    "path",
    type=click.Path(exists=False, file_okay=False, dir_okay=True),
)
def plan(path):
    """
    Launch UI to help build expedition configuration (YAML) file.

    Should you encounter any issues with using this tool, please report an issue describing the problem to the VirtualShip issue tracker at: https://github.com/OceanParcels/virtualship/issues"
    """
    _plan(Path(path))


@click.command()
@click.argument(
    "path",
    type=click.Path(exists=True, file_okay=False, dir_okay=True, readable=True),
)
@click.option(
    "--difficulty-level",
    type=click.Choice(["easy", "medium", "hard"]),
    default="easy",
    help="Set the problem level for the expedition simulation [default = easy].\n\n"
    "easy = No problems encountered during the expedition.\n\n"
    "medium = 1-2 problems encountered.\n\n"
    "hard = 1 or more problems encountered, depending on expedition length and complexity, where longer and more complex expeditions will encounter more problems.\n\n"
    "N.B.: If an expedition has already been run with problems encountered, changing the difficulty-level on a subsequent re-run will have no effect (previously encountered problems will be re-used). To select new problems (or to skip problems altogether), delete the 'problems_encountered' directory in the expedition directory before re-running with a new difficulty level.\n\n"
    "Adding instruments to your expedition will also result in new problems being selected on the next run.",
)
@click.option(
    "--from-data",
    type=str,
    default=None,
    help="Use pre-downloaded data, saved to disk, for expedition, instead of streaming directly via Copernicus Marine Service."
    "Assumes all data is stored in prescribed directory, and all variables (as listed below) are present. "
    f"Required variables are: {set(COPERNICUSMARINE_PHYS_VARIABLES + COPERNICUSMARINE_BGC_VARIABLES)} "
    "Assumes that variable names at least contain the standard Copernicus Marine variable name as a substring. "
    "Will also take the first file found containing the variable name substring. CAUTION if multiple files contain the same variable name substring.",
)
def run(path, difficulty_level, from_data):
    """Execute the expedition simulations."""
    _run(Path(path), difficulty_level, from_data)
