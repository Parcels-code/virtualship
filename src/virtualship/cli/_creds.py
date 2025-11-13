from __future__ import annotations

from pathlib import Path

import click
import pydantic
import yaml

from virtualship.errors import CredentialFileError

CREDENTIALS_FILE = "credentials.yaml"


class Credentials(pydantic.BaseModel):
    """Credentials to be used in `virtualship fetch` command."""

    COPERNICUS_USERNAME: str
    COPERNICUS_PASSWORD: str

    @classmethod
    def from_yaml(cls, path: str | Path) -> Credentials:
        """
        Load credentials from a yaml file.

        :param path: Path to the file to load from.
        :returns Credentials: The credentials.
        """
        with open(path) as file:
            data = yaml.safe_load(file)

        if not isinstance(data, dict):
            raise CredentialFileError("Credential file is of an invalid format.")

        return cls(**data)

    def dump(self) -> str:
        """
        Dump credentials to a yaml string.

        :param creds: The credentials to dump.
        :returns str: The yaml string.
        """
        return yaml.safe_dump(self.model_dump())

    def to_yaml(self, path: str | Path) -> None:
        """
        Write credentials to a yaml file.

        :param path: Path to the file to write to.
        """
        with open(path, "w") as file:
            file.write(self.dump())


def get_dummy_credentials_yaml() -> str:
    return (
        Credentials(
            COPERNICUS_USERNAME="my_username", COPERNICUS_PASSWORD="my_password"
        )
        .dump()
        .strip()
    )


def get_credentials_flow(
    username: str | None, password: str | None, creds_path: Path
) -> tuple[str, str]:
    """
    Execute flow of getting credentials for use in the `fetch` command.

    - If username and password are provided via CLI, use them (ignore the credentials file if exists).
    - If username and password are not provided, try to load them from the credentials file.
    - If no credentials are provided, print a message on how to make credentials file and prompt for credentials.

    :param username: The username provided via CLI.
    :param password: The password provided via CLI.
    :param creds_path: The path to the credentials file.
    """
    if username and password:
        if creds_path.exists():
            click.echo(
                f"Credentials file exists at '{creds_path}', but username and password are already provided. Ignoring credentials file."
            )
        return username, password

    try:
        creds = Credentials.from_yaml(creds_path)
        click.echo(f"Loaded credentials from '{creds_path}'.")
        return creds.COPERNICUS_USERNAME, creds.COPERNICUS_PASSWORD
    except FileNotFoundError:
        msg = f"""Credentials not provided. Credentials can be obtained from https://data.marine.copernicus.eu/register. Either pass in via `--username` and `--password` arguments, or via config file at '{creds_path}'. Config file should be YAML along following format:
### {creds_path}

{get_dummy_credentials_yaml().strip()}

###

Prompting for credentials instead...
"""
        click.echo(msg)
        username = click.prompt("username")
        password = click.prompt("password", hide_input=True)
        return username, password
