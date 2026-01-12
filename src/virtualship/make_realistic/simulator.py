from __future__ import annotations

import time
from pathlib import Path
from typing import TYPE_CHECKING

from yaspin import yaspin

from virtualship.cli._run import _save_checkpoint
from virtualship.instruments.types import InstrumentType
from virtualship.make_realistic.problems import GeneralProblem, InstrumentProblem
from virtualship.models.checkpoint import Checkpoint
from virtualship.utils import (
    CHECKPOINT,
)

if TYPE_CHECKING:
    from virtualship.models import Schedule


LOG_MESSAGING = {
    "first_pre_departure": "\nHang on! There could be a pre-departure problem in-port...\n\n",
    "subsequent_pre_departure": "\nOh no, another pre-departure problem has occurred...!\n\n",
    "first_during_expedition": "\nOh no, a problem has occurred during the expedition...!\n\n",
    "subsequent_during_expedition": "\nAnother problem has occurred during the expedition...!\n\n",
}


class ProblemSimulator:
    """Handle problem simulation during expedition."""

    def __init__(self, schedule: Schedule, prob_level: int, expedition_dir: str | Path):
        """Initialise ProblemSimulator with a schedule and probability level."""
        self.schedule = schedule
        self.prob_level = prob_level
        self.expedition_dir = Path(expedition_dir)

    def select_problems(
        self,
    ) -> dict[str, list[GeneralProblem | InstrumentProblem]] | None:
        """Propagate both general and instrument problems."""
        probability = self._calc_prob()
        if probability > 0.0:
            problems = {}
            problems["general"] = self._general_problem_select(probability)
            problems["instrument"] = self._instrument_problem_select(probability)
            return problems
        else:
            return None

    def execute(
        self,
        problems: dict[str, list[GeneralProblem | InstrumentProblem]],
        pre_departure: bool,
        instrument_type: InstrumentType | None = None,
        log_delay: float = 7.0,
    ):
        """Execute the selected problems, returning messaging and delay times."""
        for i, problem in enumerate(problems["general"]):
            if pre_departure and problem.pre_departure:
                print(
                    LOG_MESSAGING["first_pre_departure"]
                    if i == 0
                    else LOG_MESSAGING["subsequent_pre_departure"]
                )
            else:
                if not pre_departure and not problem.pre_departure:
                    print(
                        LOG_MESSAGING["first_during_expedition"]
                        if i == 0
                        else LOG_MESSAGING["subsequent_during_expedition"]
                    )
            with yaspin():
                time.sleep(log_delay)

            # provide problem-specific messaging
            print(problem.message)

            # save to pause expedition and save to checkpoint
            print(
                f"\n\nSIMULATION PAUSED: update your schedule (`virtualship plan`) and continue the expedition by executing the `virtualship run` command again.\nCheckpoint has been saved to {self.expedition_dir.joinpath(CHECKPOINT)}."
            )
            _save_checkpoint(
                Checkpoint(
                    past_schedule=Schedule(
                        waypoints=self.schedule.waypoints[
                            : schedule_results.failed_waypoint_i
                        ]
                    )
                ),
                self.expedition_dir,
            )

    def _propagate_general_problems(self):
        """Propagate general problems based on probability."""
        probability = self._calc_general_prob(self.schedule, prob_level=self.prob_level)
        return self._general_problem_select(probability)

    def _propagate_instrument_problems(self):
        """Propagate instrument problems based on probability."""
        probability = self._calc_instrument_prob(
            self.schedule, prob_level=self.prob_level
        )
        return self._instrument_problem_select(probability)

    def _calc_prob(self) -> float:
        """
        Calcuates probability of a general problem as function of expedition duration and prob-level.

        TODO: for now, general and instrument-specific problems have the same probability of occurence. Separating this out and allowing their probabilities to be set independently may be useful in future.
        """
        if self.prob_level == 0:
            return 0.0

    def _general_problem_select(self) -> list[GeneralProblem]:
        """Select which problems. Higher probability (tied to expedition duration) means more problems are likely to occur."""
        ...
        return []

    def _instrument_problem_select(self) -> list[InstrumentProblem]:
        """Select which problems. Higher probability (tied to expedition duration) means more problems are likely to occur."""
        # set: waypoint instruments vs. list of instrument-specific problems (automated registry)
        # will deterimne which instrument-specific problems are possible at this waypoint

        wp_instruments = self.schedule.waypoints.instruments

        return []
