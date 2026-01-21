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
    CaptainSafetyDrill,
    CTDCableJammed,
)
from virtualship.models.checkpoint import Checkpoint
from virtualship.models.expedition import Schedule
from virtualship.utils import (
    CHECKPOINT,
    EXPEDITION,
    PROBLEMS_ENCOUNTERED_DIR,
    SCHEDULE_ORIGINAL,
    _save_checkpoint,
)

if TYPE_CHECKING:
    from virtualship.make_realistic.problems.scenarios import (
        GeneralProblem,
        InstrumentProblem,
    )
import json
import random

LOG_MESSAGING = {
    "pre_departure": "Hang on! There could be a pre-departure problem in-port...",
    "during_expedition": "Oh no, a problem has occurred during the expedition, at waypoint {waypoint_i}...!",
    "simulation_paused": "Please update your schedule (`virtualship plan` or directly in {expedition_yaml}) to account for the delay at waypoint {waypoint_i} and continue the expedition by executing the `virtualship run` command again.\nCheckpoint has been saved to {checkpoint_path}.\n",
    "problem_avoided": "Phew! You had enough contingency time scheduled to avoid delays from this problem. The expedition can carry on shortly...\n",
    "pre_departure_delay": "This problem will cause a delay of {delay_duration} hours to the whole expedition schedule. Please account for this for all waypoints in your schedule (`virtualship plan` or directly in {expedition_yaml}), then continue the expedition by executing the `virtualship run` command again.\n",
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
        instrument_type: InstrumentType | None = None,
        log_delay: float = 7.0,
    ):
        """
        Execute the selected problems, returning messaging and delay times.

        N.B. the problem_waypoint_i is different to the failed_waypoint_i defined in the Checkpoint class; the failed_waypoint_i is the waypoint index after the problem_waypoint_i where the problem occurred, as this is when scheduling issues would be encountered.
        """
        # TODO: integration with which zarr files have been written so far?
        # TODO: logic to determine whether user has made the necessary changes to the schedule to account for the problem's delay_duration when next running the simulation... (does this come in here or _run?)
        # TODO: logic for whether the user has already scheduled in enough contingency time to account for the problem's delay_duration, and they get a well done message if so
        # TODO: need logic for if the problem can reoccur or not / and or that it has already occurred and has been addressed

        # TODO: re: prob levels:
        # 0 = no problems
        # 1 = only one problem in expedition (either pre-departure or during expedition, general or instrument) [and set this to DEFAULT prob level]
        # 2 = multiple problems can occur (general and instrument), but only one pre-departure problem allowed

        # TODO: what to do about fact that students can avoid all problems by just scheduling in enough contingency time??
        # this should probably be a learning point though, so maybe it's fine...
        #! though could then ensure that if they pass because of contingency time, they definitely get a pre-depature problem...?
        # this would all probably have to be a bit asynchronous, which might make things more complicated...

        #! TODO: logic as well for case where problem can reoccur but it can only reoccur at a waypoint different to the one it has already occurred at

        # TODO: N.B. there is not logic currently controlling how many problems can occur in total during an expedition; at the moment it can happen every time the expedition is run if it's a different waypoint / problem combination

        general_problems = problems["general"]
        instrument_problems = problems["instrument"]

        # allow only one pre-departure problem to occur
        pre_departure_problems = [p for p in general_problems if p.pre_departure]
        if len(pre_departure_problems) > 1:
            to_keep = random.choice(pre_departure_problems)
            general_problems = [
                p for p in general_problems if not p.pre_departure or p is to_keep
            ]
        # ensure any pre-departure problem is first in list
        general_problems.sort(key=lambda x: x.pre_departure, reverse=True)

        # TODO: make the log output stand out more visually
        # general problems
        for gproblem in general_problems:
            # determine problem waypoint index (random if during expedition)
            problem_waypoint_i = (
                None
                if gproblem.pre_departure
                else np.random.randint(
                    0, len(self.schedule.waypoints) - 1
                )  # last waypoint excluded (would not impact any future scheduling)
            )

            # mark problem by unique hash and log to json, use to assess whether problem has already occurred
            gproblem_hash = self._make_hash(
                gproblem.message + str(problem_waypoint_i), 8
            )
            hash_path = Path(
                self.expedition_dir
                / f"{PROBLEMS_ENCOUNTERED_DIR}/problem_{gproblem_hash}.json"
            )
            if hash_path.exists():
                continue  # problem * waypoint combination has already occurred; don't repeat
            else:
                self._hash_to_json(
                    gproblem, gproblem_hash, problem_waypoint_i, hash_path
                )

            if gproblem.pre_departure:
                alert_msg = LOG_MESSAGING["pre_departure"]

            else:
                alert_msg = LOG_MESSAGING["during_expedition"].format(
                    waypoint_i=int(problem_waypoint_i) + 1
                )

            # log problem occurrence, save to checkpoint, and pause simulation
            self._log_problem(gproblem, problem_waypoint_i, alert_msg, log_delay)

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
        return [
            CaptainSafetyDrill,
        ]  # TODO: temporary placeholder!!

    def _instrument_problem_select(self, probability) -> list[InstrumentProblem]:
        """Select which problems. Higher probability (tied to expedition duration) means more problems are likely to occur."""
        # set: waypoint instruments vs. list of instrument-specific problems (automated registry)
        # will deterimne which instrument-specific problems are possible at this waypoint

        # wp_instruments = self.schedule.waypoints.instruments

        return [CTDCableJammed]

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

            # handle first waypoint separately (no previous waypoint to provide contingency time, or rather the previous waypoint ends up being the -1th waypoint which is non-sensical)
            if problem_waypoint_i == 0:
                print(result_msg)

            # all other waypoints
            else:
                # check if enough contingency time has been scheduled to avoid delay affecting future waypoints
                with yaspin(text="Assessing impact on expedition schedule..."):
                    time.sleep(5.0)
                problem_waypoint_time = self.schedule.waypoints[problem_waypoint_i].time
                next_waypoint_time = self.schedule.waypoints[
                    problem_waypoint_i + 1
                ].time
                time_diff = (
                    next_waypoint_time - problem_waypoint_time
                ).total_seconds() / 3600.0  # [hours]
                if time_diff >= problem.delay_duration.total_seconds() / 3600.0:
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
            self._cache_original_schedule(self.schedule, schedule_original_path)

        # pause simulation
        sys.exit(0)

    def _make_checkpoint(self, failed_waypoint_i: int | None = None) -> Checkpoint:
        """Make checkpoint, also handling pre-departure."""
        fpi = None if failed_waypoint_i is None else failed_waypoint_i
        return Checkpoint(past_schedule=self.schedule, failed_waypoint_i=fpi)

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
