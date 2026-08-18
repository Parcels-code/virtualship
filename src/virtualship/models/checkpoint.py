"""Checkpoint class."""

from __future__ import annotations

from pathlib import Path

import pydantic
import yaml

from virtualship.errors import CheckpointError
from virtualship.instruments.types import InstrumentType
from virtualship.models.expedition import Schedule
from virtualship.utils import _get_public_wp


class _YamlDumper(yaml.SafeDumper):
    pass


_YamlDumper.add_representer(
    InstrumentType, lambda dumper, data: dumper.represent_data(data.value)
)


class ActiveProblem(pydantic.BaseModel):
    """Runtime state of a problem halting simulation."""

    message: str
    problem_wp_i: int | None  # noqa; index of the waypoint that caused a problem (if any)
    delay_duration_hours: float
    resolved: bool = False


class Checkpoint(pydantic.BaseModel):
    """A checkpoint of the schedule simulation storing past schedule state and any active problem that halted execution."""

    past_schedule: Schedule
    failed_wp_i: int | None = None  # noqa; index of the waypoint that could not be reached in time
    active_problem: ActiveProblem | None = None

    @property
    def problem_wp_i(self) -> int | None:
        """Delegate to active_problem to avoid duplication."""
        return self.active_problem.problem_wp_i if self.active_problem else None

    def get_effective_failed_wp_i(self) -> int | None:
        """Return the index of the waypoint that failed or could not be reached."""
        if self.failed_wp_i is not None:
            return self.failed_wp_i
        if self.problem_wp_i is not None:
            return self.problem_wp_i + 1
        return None

    def verify_past_schedule(self, new_schedule: Schedule) -> None:
        """Core structural check: ensure past history hasn't been edited."""
        failed_wp_i = self.get_effective_failed_wp_i()
        if failed_wp_i is None:
            return

        public_failed_wp = _get_public_wp(failed_wp_i, self.past_schedule.waypoints)

        if (
            new_schedule.waypoints[: int(failed_wp_i)]
            != self.past_schedule.waypoints[: int(failed_wp_i)]
        ):
            raise CheckpointError(
                f"Past waypoints in schedule have been changed! Restore past schedule "
                f"and only change future waypoints (waypoint {int(public_failed_wp)} onwards)."
            )

    def to_yaml(self, file_path: str | Path) -> None:
        """Write checkpoint to YAML file."""
        with open(file_path, "w", encoding="utf-8") as file:
            yaml.dump(self.model_dump(by_alias=True), file, Dumper=_YamlDumper)

    @classmethod
    def from_yaml(cls, file_path: str | Path) -> Checkpoint:
        """Load checkpoint from YAML file."""
        with open(file_path, encoding="utf-8") as file:
            data = yaml.safe_load(file)
        return Checkpoint(**data)
