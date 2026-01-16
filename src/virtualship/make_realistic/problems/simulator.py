from __future__ import annotations

import hashlib
import os
import sys
import time
from pathlib import Path
from typing import TYPE_CHECKING

import numpy as np
from yaspin import yaspin

from virtualship.instruments.types import InstrumentType
from virtualship.make_realistic.problems.scenarios import (
    CTDCableJammed,
    FoodDeliveryDelayed,
)
from virtualship.models.checkpoint import Checkpoint
from virtualship.utils import CHECKPOINT, _save_checkpoint

if TYPE_CHECKING:
    from virtualship.make_realistic.problems.scenarios import (
        GeneralProblem,
        InstrumentProblem,
    )
    from virtualship.models import Schedule
import json

LOG_MESSAGING = {
    "first_pre_departure": "Hang on! There could be a pre-departure problem in-port...",
    "subsequent_pre_departure": "Oh no, another pre-departure problem has occurred...!\n",
    "first_during_expedition": "Oh no, a problem has occurred during at waypoint {waypoint_i}...!\n",
    "subsequent_during_expedition": "Another problem has occurred during the expedition... at waypoint {waypoint_i}!\n",
    "simulation_paused": "SIMULATION PAUSED: update your schedule (`virtualship plan`) and continue the expedition by executing the `virtualship run` command again.\nCheckpoint has been saved to {checkpoint_path}.\n",
    "problem_avoided": "Phew! You had enough contingency time scheduled to avoid delays from this problem. The expedition can carry on.\n",
    "pre_departure_delay": "This problem will cause a delay of **{delay_duration} hours** to the whole expedition schedule. Please account for this for **all** waypoints in your schedule (`virtualship plan`), then continue the expedition by executing the `virtualship run` command again.\n",
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
        # TODO: whether a problem can reoccur or not needs to be handled here too!
        probability = self._calc_prob()
        probability = 1.0  # TODO: temporary override for testing!!
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
        # TODO: integration with which zarr files have been written so far?
        # TODO: logic to determine whether user has made the necessary changes to the schedule to account for the problem's delay_duration when next running the simulation... (does this come in here or _run?)
        # TODO: logic for whether the user has already scheduled in enough contingency time to account for the problem's delay_duration, and they get a well done message if so
        # TODO: need logic for if the problem can reoccur or not / and or that it has already occurred and has been addressed

        #! TODO: logic as well for case where problem can reoccur but it can only reoccur at a waypoint different to the one it has already occurred at

        # TODO: make the log output stand out more visually
        # general problems
        for i, gproblem in enumerate(problems["general"]):
            # determine failed waypoint index (random if during expedition)
            failed_waypoint_i = (
                np.nan
                if pre_departure
                else np.random.randint(0, len(self.schedule.waypoints) - 1)
            )

            # TODO: some kind of handling for deleting directory if ... simulation encounters error? or just leave it to user to delete manually if they want to restart from scratch?
            # mark problem by unique hash and log to json, use to assess whether problem has already occurred
            gproblem_hash = self._make_hash(
                gproblem.message + str(failed_waypoint_i), 8
            )
            hash_path = Path(
                self.expedition_dir
                / f"problems_encountered/problem_{gproblem_hash}.json"
            )
            if hash_path.exists():
                continue  # problem * waypoint combination has already occurred; don't repeat
            else:
                self._hash_to_json(
                    gproblem, gproblem_hash, failed_waypoint_i, hash_path
                )

            if pre_departure and gproblem.pre_departure:
                alert_msg = (
                    LOG_MESSAGING["first_pre_departure"]
                    if i == 0
                    else LOG_MESSAGING["subsequent_pre_departure"]
                )

            elif not pre_departure and not gproblem.pre_departure:
                alert_msg = (
                    LOG_MESSAGING["first_during_expedition"].format(
                        waypoint_i=gproblem.waypoint_i
                    )
                    if i == 0
                    else LOG_MESSAGING["subsequent_during_expedition"].format(
                        waypoint_i=gproblem.waypoint_i
                    )
                )

            else:
                continue  # problem does not occur (e.g. wrong combination of pre-departure vs. problem can only occur during expedition)

            # log problem occurrence, save to checkpoint, and pause simulation
            self._log_problem(gproblem, failed_waypoint_i, alert_msg, log_delay)

        # instrument problems
        for i, problem in enumerate(problems["instrument"]):
            pass  # TODO: implement!!
            # TODO: similar logic to above for instrument-specific problems... or combine?

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

    def _general_problem_select(self, probability) -> list[GeneralProblem]:
        """Select which problems. Higher probability (tied to expedition duration) means more problems are likely to occur."""
        return [FoodDeliveryDelayed]  # TODO: temporary placeholder!!

    def _instrument_problem_select(self, probability) -> list[InstrumentProblem]:
        """Select which problems. Higher probability (tied to expedition duration) means more problems are likely to occur."""
        # set: waypoint instruments vs. list of instrument-specific problems (automated registry)
        # will deterimne which instrument-specific problems are possible at this waypoint

        # wp_instruments = self.schedule.waypoints.instruments

        return [CTDCableJammed]

    def _log_problem(
        self,
        problem: GeneralProblem | InstrumentProblem,
        failed_waypoint_i: int | float,
        alert_msg: str,
        log_delay: float,
    ):
        """Log problem occurrence with spinner and delay, save to checkpoint, write hash."""
        time.sleep(3.0)  # brief pause before spinner
        with yaspin(text=alert_msg) as spinner:
            time.sleep(log_delay)
            spinner.ok("💥 ")

        print("\nPROBLEM ENCOUNTERED: " + problem.message)

        if np.isnan(failed_waypoint_i):  # pre-departure problem
            print(
                "\nRESULT: "
                + LOG_MESSAGING["pre_departure_delay"].format(
                    delay_duration=problem.delay_duration.total_seconds() / 3600.0
                )
            )
        else:  # problem occurring during expedition
            print(
                "\nRESULT: "
                + LOG_MESSAGING["simulation_paused"].format(
                    checkpoint_path=self.expedition_dir.joinpath(CHECKPOINT)
                )
            )
            # check if enough contingency time has been scheduled to avoid delay
            print("\nAssessing impact on expedition schedule...\n")
            failed_waypoint_time = self.schedule.waypoints[failed_waypoint_i].time
            previous_waypoint_time = self.schedule.waypoints[failed_waypoint_i - 1].time
            time_diff = (
                failed_waypoint_time - previous_waypoint_time
            ).total_seconds() / 3600.0  # in hours
            if time_diff >= problem.delay_duration.total_seconds() / 3600.0:
                print(LOG_MESSAGING["problem_avoided"])
                return
            else:
                print(
                    f"\nNot enough contingency time scheduled to avoid delay of {problem.delay_duration.total_seconds() / 3600.0} hours.\n"
                )

        # save checkpoint
        checkpoint = self._make_checkpoint(failed_waypoint_i)
        _save_checkpoint(checkpoint, self.expedition_dir)

        # cache original schedule for reference and/or restoring later if needed
        schedule_original_path = (
            self.expedition_dir / "problems_encountered" / "schedule_original.yaml"
        )
        if os.path.exists(schedule_original_path) is False:
            self._cache_original_schedule(self.schedule, schedule_original_path)

        # pause simulation
        sys.exit(0)

    def _make_checkpoint(self, failed_waypoint_i: int | float = np.nan):
        """Make checkpoint, also handling pre-departure."""
        if np.isnan(failed_waypoint_i):  # handles pre-departure problems
            checkpoint = Checkpoint(
                past_schedule=self.schedule
            )  # use full schedule as past schedule
        else:
            checkpoint = Checkpoint(
                past_schedule=Schedule(
                    waypoints=self.schedule.waypoints[:failed_waypoint_i]
                )
            )
        return checkpoint

    def _make_hash(self, s: str, length: int) -> str:
        """Make unique hash for problem occurrence."""
        assert length % 2 == 0, "Length must be even."
        half_length = length // 2
        return hashlib.shake_128(s.encode("utf-8")).hexdigest(half_length)

    def _hash_to_json(
        self,
        problem: InstrumentProblem | GeneralProblem,
        problem_hash: str,
        failed_waypoint_i: int | float,
        hash_path: Path,
    ) -> dict:
        """Convert problem details + hash to json."""
        os.makedirs(self.expedition_dir / "problems_encountered", exist_ok=True)
        hash_data = {
            "problem_hash": problem_hash,
            "message": problem.message,
            "failed_waypoint_i": failed_waypoint_i,
            "delay_duration_hours": problem.delay_duration.total_seconds() / 3600.0,
            "timestamp": time.strftime("%Y-%m-%d %H:%M:%S", time.localtime()),
            "resolved": False,
        }
        with open(hash_path, "w") as f:
            json.dump(hash_data, f, indent=4)

    def _cache_original_schedule(self, schedule: Schedule, path: Path | str):
        """Cache original schedule to file for reference, as a checkpoint object."""
        schedule_original = Checkpoint(past_schedule=schedule)
        schedule_original.to_yaml(path)
        print(f"\nOriginal schedule cached to {path}.\n")
