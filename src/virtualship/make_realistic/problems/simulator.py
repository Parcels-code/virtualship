from __future__ import annotations

import hashlib
import json
import os
import random
import sys
import time
from pathlib import Path
from typing import TYPE_CHECKING

import numpy as np
from yaspin import yaspin

from virtualship.instruments.types import InstrumentType
from virtualship.make_realistic.problems.scenarios import (
    CTDCableJammed,
    GeneralProblem,
    InstrumentProblem,
)
from virtualship.models.checkpoint import Checkpoint
from virtualship.utils import (
    CHECKPOINT,
    EXPEDITION,
    PROBLEMS_ENCOUNTERED_DIR,
    PROJECTION,
    SCHEDULE_ORIGINAL,
    _calc_sail_time,
    _save_checkpoint,
)

if TYPE_CHECKING:
    from virtualship.models.expedition import Expedition, Schedule

LOG_MESSAGING = {
    "pre_departure": "Hang on! There could be a pre-departure problem in-port...",
    "during_expedition": "Oh no, a problem has occurred during the expedition, at waypoint {waypoint_i}...!",
    "simulation_paused": "Please update your schedule (`virtualship plan` or directly in {expedition_yaml}) to account for the delay at waypoint {waypoint_i} and continue the expedition by executing the `virtualship run` command again.\nCheckpoint has been saved to {checkpoint_path}.\n",
    "pre_departure_delay": "This problem will cause a delay of {delay_duration} hours to the whole expedition schedule. Please account for this for all waypoints in your schedule (`virtualship plan` or directly in {expedition_yaml}), then continue the expedition by executing the `virtualship run` command again.\n",
    "problem_avoided": "Phew! You had enough contingency time scheduled to avoid delays from this problem. The expedition can carry on shortly...\n",
}


class ProblemSimulator:
    """Handle problem simulation during expedition."""

    def __init__(
        self, expedition: Expedition, prob_level: int, expedition_dir: str | Path
    ):
        """Initialise ProblemSimulator with a schedule and probability level."""
        self.expedition = expedition
        self.prob_level = prob_level
        self.expedition_dir = Path(expedition_dir)

    def select_problems(
        self,
        prob_level,
        instruments_in_expedition: set[InstrumentType],
    ) -> dict[str, list[GeneralProblem | InstrumentProblem]] | None:
        """Propagate both general and instrument problems."""
        # TODO: whether a problem can reoccur or not needs to be handled here too!
        if prob_level > 0:
            return self._problem_select(prob_level, instruments_in_expedition)

    def execute(
        self,
        problems: dict[str, list[GeneralProblem | InstrumentProblem]],
        instrument_type_validation: InstrumentType | None = None,
        log_delay: float = 7.0,
    ):
        """
        Execute the selected problems, returning messaging and delay times.

        N.B. a problem_waypoint_i is different to a failed_waypoint_i defined in the Checkpoint class; failed_waypoint_i is the waypoint index after the problem_waypoint_i where the problem occurred, as this is when scheduling issues would be encountered.
        """
        # TODO: re: prob levels:
        # 0 = no problems
        # 1 = only one problem in expedition (either pre-departure or during expedition, general or instrument) [and set this to DEFAULT prob level]
        # 2 = multiple problems can occur (general and instrument), but only one pre-departure problem allowed

        # TODO: N.B. there is not logic currently controlling how many problems can occur in total during an expedition; at the moment it can happen every time the expedition is run if it's a different waypoint / problem combination

        #! TODO: what happens if students decide to re-run the expedition multiple times with slightly changed set-ups to try to e.g. get more measurements? Maybe it should be that problems are ignored if the exact expedition.yaml has been run before, and if there's any changes to the expedition.yaml
        # TODO: for this reason, `problems_encountered` dir should be housed in `results` dir along with a cache of the expedition.yaml used for that run...
        # TODO: and the results dir given a unique name which can be used to check against when re-running the expedition?

        # allow only one pre-departure problem to occur (only GeneralProblems can be pre-departure problems)
        pre_departure_problems = [p for p in problems if isinstance(p, GeneralProblem)]
        if len(pre_departure_problems) > 1:
            to_keep = random.choice(pre_departure_problems)
            problems = [
                p
                for p in problems
                if not getattr(p, "pre_departure", False) or p is to_keep
            ]
        problems.sort(
            key=lambda p: getattr(p, "pre_departure", False), reverse=True
        )  # ensure any problem with pre_departure=True is first; default to pre_departure=False if attribute not present (as is the case for InstrumentProblem's)

        # TODO: make the log output stand out more visually
        for p in problems:
            # skip if instrument problem but `p.instrument_type` does not match `instrument_type_validation`
            if (
                isinstance(p, InstrumentProblem)
                and p.instrument_type is not instrument_type_validation
            ):
                continue

            problem_waypoint_i = (
                None
                if getattr(p, "pre_departure", False)
                else np.random.randint(
                    0, len(self.expedition.schedule.waypoints) - 1
                )  # last waypoint excluded (would not impact any future scheduling)
            )

            # TODO: double check the hashing still works as expected when problem_waypoint_i is None (i.e. pre-departure problem)
            problem_hash = self._make_hash(p.message + str(problem_waypoint_i), 8)
            hash_path = Path(
                self.expedition_dir
                / f"{PROBLEMS_ENCOUNTERED_DIR}/problem_{problem_hash}.json"
            )
            if hash_path.exists():
                continue  # problem * waypoint combination has already occurred; don't repeat
            else:
                self._hash_to_json(p, problem_hash, problem_waypoint_i, hash_path)

            if isinstance(p, GeneralProblem) and p.pre_departure:
                alert_msg = LOG_MESSAGING["pre_departure"]

            else:
                alert_msg = LOG_MESSAGING["during_expedition"].format(
                    waypoint_i=int(problem_waypoint_i) + 1
                )

            # log problem occurrence, save to checkpoint, and pause simulation
            self._log_problem(p, problem_waypoint_i, alert_msg, log_delay)

    def _problem_select(
        self, prob_level, instruments_in_schedule
    ) -> list[GeneralProblem | InstrumentProblem]:
        """Select which problems (selected from general or instrument problems). Higher probability (tied to expedition duration) means more problems are likely to occur."""
        return [CTDCableJammed]  # TODO: temporary placeholder!!

    def _log_problem(
        self,
        problem: GeneralProblem | InstrumentProblem,
        problem_waypoint_i: int | None,
        alert_msg: str,
        log_delay: float,
    ):
        """Log problem occurrence with spinner and delay, save to checkpoint, write hash."""
        time.sleep(3.0)  # brief pause before spinner
        with yaspin(text=alert_msg) as spinner:
            time.sleep(log_delay)
            spinner.ok("💥 ")

        print("\nPROBLEM ENCOUNTERED: " + problem.message + "\n")

        if problem_waypoint_i is None:  # pre-departure problem
            print(
                "\nRESULT: "
                + LOG_MESSAGING["pre_departure_delay"].format(
                    delay_duration=problem.delay_duration.total_seconds() / 3600.0,
                    expedition_yaml=EXPEDITION,
                )
            )

        else:  # problem occurring during expedition
            result_msg = "\nRESULT: " + LOG_MESSAGING["simulation_paused"].format(
                waypoint_i=int(problem_waypoint_i) + 1,
                expedition_yaml=EXPEDITION,
                checkpoint_path=self.expedition_dir.joinpath(CHECKPOINT),
            )

            # check if enough contingency time has been scheduled to avoid delay affecting future waypoints
            with yaspin(text="Assessing impact on expedition schedule..."):
                time.sleep(5.0)
            problem_waypoint_time = self.expedition.schedule.waypoints[
                problem_waypoint_i
            ].time
            next_waypoint_time = self.expedition.schedule.waypoints[
                problem_waypoint_i + 1
            ].time
            time_diff = (
                next_waypoint_time - problem_waypoint_time
            ).total_seconds() / 3600.0  # [hours]
            sail_time = (
                _calc_sail_time(
                    self.expedition.schedule.waypoints[problem_waypoint_i],
                    self.expedition.schedule.waypoints[problem_waypoint_i + 1],
                    ship_speed_knots=self.expedition.ship_config.ship_speed_knots,
                    projection=PROJECTION,
                ).total_seconds()
                / 3600.0
            )  # [hours]
            if (
                time_diff
                >= (problem.delay_duration.total_seconds() / 3600.0) + sail_time
            ):
                print(LOG_MESSAGING["problem_avoided"])
                # give users time to read message before simulation continues
                with yaspin():
                    time.sleep(7.0)
                return

            else:
                print(
                    f"\nNot enough contingency time scheduled to mitigate delay of {problem.delay_duration.total_seconds() / 3600.0} hours occuring at waypoint {problem_waypoint_i + 1} (future waypoints would be reached too late).\n"
                )
                print(result_msg)

        # save checkpoint
        checkpoint = self._make_checkpoint(
            failed_waypoint_i=problem_waypoint_i + 1
        )  # failed waypoint index then becomes the one after the one where the problem occurred; this is when scheduling issues would be run into
        _save_checkpoint(checkpoint, self.expedition_dir)

        # cache original schedule for reference and/or restoring later if needed (checkpoint can be overwritten if multiple problems occur so is not a persistent record of original schedule)
        schedule_original_path = (
            self.expedition_dir / PROBLEMS_ENCOUNTERED_DIR / SCHEDULE_ORIGINAL
        )
        if os.path.exists(schedule_original_path) is False:
            self._cache_original_schedule(
                self.expedition.schedule, schedule_original_path
            )

        # pause simulation
        sys.exit(0)

    def _make_checkpoint(self, failed_waypoint_i: int | None = None) -> Checkpoint:
        """Make checkpoint, also handling pre-departure."""
        fpi = None if failed_waypoint_i is None else failed_waypoint_i
        return Checkpoint(past_schedule=self.expedition.schedule, failed_waypoint_i=fpi)

    def _make_hash(self, s: str, length: int) -> str:
        """Make unique hash for problem occurrence."""
        assert length % 2 == 0, "Length must be even."
        half_length = length // 2
        return hashlib.shake_128(s.encode("utf-8")).hexdigest(half_length)

    def _hash_to_json(
        self,
        problem: InstrumentProblem | GeneralProblem,
        problem_hash: str,
        failed_waypoint_i: int | None,
        hash_path: Path,
    ) -> dict:
        """Convert problem details + hash to json."""
        os.makedirs(self.expedition_dir / PROBLEMS_ENCOUNTERED_DIR, exist_ok=True)
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
