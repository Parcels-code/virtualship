from pathlib import Path

import click

from virtualship.cli._plan import _plan
from virtualship.cli._run import _run
from virtualship.utils import (
    COPERNICUSMARINE_BGC_VARIABLES,
    COPERNICUSMARINE_PHYS_VARIABLES,
    EXPEDITION,
    get_example_expedition,
    mfp_to_yaml,
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
def init(path, from_mfp):
    """
    Initialize a directory for a new expedition, with an expedition.yaml file.

    If --mfp-file is provided, it will generate the expedition.yaml from the MPF file instead.
    """
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
        mfp_to_yaml(mfp_file, expedition)
        click.echo(
            "\n⚠️  The generated schedule does not contain TIME values or INSTRUMENT selections.  ⚠️"
            "\n\nNow please either use the `\033[4mvirtualship plan\033[0m` app to complete the schedule configuration, "
            "\nOR edit 'expedition.yaml' and manually add the necessary time values and instrument selections under the 'schedule' heading."
            "\n\nIf editing 'expedition.yaml' manually:"
            "\n\n🕒  Expected time format: 'YYYY-MM-DD HH:MM:SS' (e.g., '2023-10-20 01:00:00')."
            "\n\n🌡️   Expected instrument(s) format: one line per instrument e.g."
            f"\n\n{' ' * 15}waypoints:\n{' ' * 15}- instrument:\n{' ' * 19}- CTD\n{' ' * 19}- ARGO_FLOAT\n"
        )
    else:
        # Create a default example expedition YAML
        expedition.write_text(get_example_expedition())

    click.echo(f"Created '{expedition.name}' at {path}.")


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
    "--from-data",
    type=str,
    default=None,
    help="Use pre-downloaded data, saved to disk, for expedition, instead of streaming directly via Copernicus Marine"
    "Assumes all data is stored in prescribed directory, and all variables (as listed below) are present."
    f"Required variables are: {set(COPERNICUSMARINE_PHYS_VARIABLES + COPERNICUSMARINE_BGC_VARIABLES)}"
    "Assumes that variable names at least contain the standard Copernicus Marine variable name as a substring."
    "Will also take the first file found containing the variable name substring. CAUTION if multiple files contain the same variable name substring.",
)
def run(path, from_data):
    """Execute the expedition simulations."""
    _run(Path(path), from_data)
