import warnings

# TODO: remove this when Parcels v4 is no longer alpha and the warning is no longer issued
warnings.filterwarnings(
    "ignore",
    message="This is an alpha version of Parcels v4.*",
    category=UserWarning,
)

import click  # noqa: E402

from . import commands  # noqa: E402


@click.group()
@click.version_option()
def cli():
    pass


cli.add_command(commands.init)
cli.add_command(commands.plan)
cli.add_command(commands.run)

if __name__ == "__main__":
    cli()
