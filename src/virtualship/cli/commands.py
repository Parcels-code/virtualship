from pathlib import Path

import click

from virtualship import utils
from virtualship.cli._plan import _plan
from virtualship.cli._run import _run
from virtualship.utils import (
    EXPEDITION,
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
        expedition.write_text(utils.get_example_expedition())

    click.echo(f"Created '{expedition.name}' at {path}.")


@click.command()
@click.argument(
    "path",
    type=click.Path(exists=False, file_okay=False, dir_okay=True),
)
def plan(path):
    """
    Launch UI to help build schedule and ship config files.

    Should you encounter any issues with using this tool, please report an issue describing the problem to the VirtualShip issue tracker at: https://github.com/OceanParcels/virtualship/issues"
    """
    _plan(Path(path))


# TODO: also add option to 'stream' via link to dir elsewhere, e.g. simlink or path to data stored elsewhere that isn't expedition dir!
@click.command()
@click.argument(
    "path",
    type=click.Path(exists=True, file_okay=False, dir_okay=True, readable=True),
)
def run(path):
    """Run the expedition."""
    _run(Path(path))
