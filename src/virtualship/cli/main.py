import click

from . import commands


@click.group()
@click.version_option()
def cli():
    pass


cli.add_command(commands.init)
cli.add_command(commands.plan)
cli.add_command(commands.run)

if __name__ == "__main__":
    cli()
