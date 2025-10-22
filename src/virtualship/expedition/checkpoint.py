"""Checkpoint class."""

from __future__ import annotations

from pathlib import Path

import pydantic
import yaml

from virtualship.errors import CheckpointError
from virtualship.instruments.master import InstrumentType
from virtualship.models import Schedule


class _YamlDumper(yaml.SafeDumper):
    pass


_YamlDumper.add_representer(
    InstrumentType, lambda dumper, data: dumper.represent_data(data.value)
)


class Checkpoint(pydantic.BaseModel):
    """
    A checkpoint of schedule simulation.

    Copy of the schedule until where the simulation proceeded without troubles.
    """

    past_schedule: Schedule

    def to_yaml(self, file_path: str | Path) -> None:
        """
        Write checkpoint to yaml file.

        :param file_path: Path to the file to write to.
        """
        with open(file_path, "w") as file:
            yaml.dump(self.model_dump(by_alias=True), file, Dumper=_YamlDumper)

    @classmethod
    def from_yaml(cls, file_path: str | Path) -> Checkpoint:
        """
        Load checkpoint from yaml file.

        :param file_path: Path to the file to load from.
        :returns: The checkpoint.
        """
        with open(file_path) as file:
            data = yaml.safe_load(file)
        return Checkpoint(**data)

    def verify(self, schedule: Schedule) -> None:
        """
        Verify that the given schedule matches the checkpoint's past schedule.

        This method checks if the waypoints in the given schedule match the waypoints
        in the checkpoint's past schedule up to the length of the past schedule.
        If there's a mismatch, it raises a CheckpointError.

        :param schedule: The schedule to verify against the checkpoint.
        :type schedule: Schedule
        :raises CheckpointError: If the past waypoints in the given schedule
                                 have been changed compared to the checkpoint.
        :return: None
        """
        if (
            not schedule.waypoints[: len(self.past_schedule.waypoints)]
            == self.past_schedule.waypoints
        ):
            raise CheckpointError(
                "Past waypoints in schedule have been changed! Restore past schedule and only change future waypoints."
            )
