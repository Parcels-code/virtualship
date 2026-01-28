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
    CaptainSafetyDrill,
    CTDCableJammed,
    FoodDeliveryDelayed,
    GeneralProblem,
    InstrumentProblem,
)
from virtualship.models.checkpoint import Checkpoint
from virtualship.utils import (
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
    "during_expedition": "Oh no, a problem has occurred during the expedition, at waypoint {waypoint}...!",
    "schedule_problems": "This problem will cause a delay of {delay_duration} hours {problem_wp}. The next waypoint therefore cannot be reached in time. Please account for this in your schedule (`virtualship plan` or directly in {expedition_yaml}), then continue the expedition by executing the `virtualship run` command again.\n",
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
    ) -> list[GeneralProblem | InstrumentProblem] | None:
        """Propagate both general and instrument problems."""
        # TODO: whether a problem can reoccur or not needs to be handled here too!
        if prob_level > 0:
            return [
                CTDCableJammed,
                FoodDeliveryDelayed,
                CaptainSafetyDrill,
            ]  # TODO: temporary placeholder!!

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
        # 2 = multiple problems can occur (general and instrument; total determined by the length of the expedition), but only one pre-departure problem allowed

        # TODO: N.B. there is not logic currently controlling how many problems can occur in total during an expedition; at the moment it can happen every time the expedition is run if it's a different waypoint / problem combination
        #! TODO: may want to ensure duplicate problem types are removed; even if they could theoretically occur at different waypoints, so as not to inundate users...

        #! TODO: what happens if students decide to re-run the expedition multiple times with slightly changed set-ups to try to e.g. get more measurements? Maybe it should be that problems are ignored if the exact expedition.yaml has been run before, and if there's any changes to the expedition.yaml
        # TODO: for this reason, `problems_encountered` dir should be housed in `results` dir along with a cache of the expedition.yaml used for that run...
        # TODO: and the results dir given a unique name which can be used to check against when re-running the expedition?

        # allow only one pre-departure problem to occur (only GeneralProblems can be pre-departure problems)

        pre_departure_problems = [
            p for p in problems if issubclass(p, GeneralProblem) and p.pre_departure
        ]
        if len(pre_departure_problems) > 1:  # keep only one pre-departure problem
            to_keep = random.choice(pre_departure_problems)  # pick one at random
            problems = [
                p
                for p in problems
                if not getattr(p, "pre_departure", False) or p is to_keep
            ]

        # map each problem to a [random] waypoint (or None if pre-departure)
        waypoint_idxs = []
        for p in problems:
            if getattr(p, "pre_departure", False):
                waypoint_idxs.append(None)
            else:
                waypoint_idxs.append(
                    np.random.randint(0, len(self.expedition.schedule.waypoints) - 1)
                )  # last waypoint excluded (would not impact any future scheduling)

        # air problems with their waypoint indices and sort by waypoint index (pre-departure first)
        paired = sorted(
            zip(problems, waypoint_idxs, strict=True),
            key=lambda x: (x[1] is not None, x[1] if x[1] is not None else -1),
        )
        problems_sorted = {
            "problem_class": [p for p, _ in paired],
            "waypoint_i": [w for _, w in paired],
        }

        # TODO: make the log output stand out more visually
        for problem, problem_waypoint_i in zip(
            problems_sorted["problem_class"], problems_sorted["waypoint_i"], strict=True
        ):
            # skip if instrument problem but `p.instrument_type` does not match `instrument_type_validation` (i.e. the current instrument being simulated in the expedition, e.g. from _run.py)
            if (
                issubclass(problem, InstrumentProblem)
                and problem.instrument_type is not instrument_type_validation
            ):
                continue

            # TODO: double check the hashing still works as expected when problem_waypoint_i is None (i.e. pre-departure problem)
            problem_hash = self._make_hash(problem.message + str(problem_waypoint_i), 8)
            hash_path = Path(
                self.expedition_dir
                / f"{PROBLEMS_ENCOUNTERED_DIR}/problem_{problem_hash}.json"
            )
            if hash_path.exists():
                continue  # problem * waypoint combination has already occurred; don't repeat

            if issubclass(problem, GeneralProblem) and problem.pre_departure:
                alert_msg = LOG_MESSAGING["pre_departure"]

            else:
                alert_msg = LOG_MESSAGING["during_expedition"].format(
                    waypoint=int(problem_waypoint_i) + 1
                )

            # log problem occurrence, save to checkpoint, and pause simulation
            self._log_problem(
                problem,
                problem_waypoint_i,
                alert_msg,
                problem_hash,
                hash_path,
                log_delay,
            )

    def _log_problem(
        self,
        problem: GeneralProblem | InstrumentProblem,
        problem_waypoint_i: int | None,
        alert_msg: str,
        problem_hash: str,
        hash_path: Path,
        log_delay: float,
    ):
        """Log problem occurrence with spinner and delay, save to checkpoint, write hash."""
        time.sleep(3.0)  # brief pause before spinner
        with yaspin(text=alert_msg) as spinner:
            time.sleep(log_delay)
            spinner.ok("💥 ")

        print("\nPROBLEM ENCOUNTERED: " + problem.message + "\n")

        result_msg = "\nRESULT: " + LOG_MESSAGING["schedule_problems"].format(
            delay_duration=problem.delay_duration.total_seconds() / 3600.0,
            problem_wp=(
                "in-port"
                if problem_waypoint_i is None
                else f"at waypoint {problem_waypoint_i + 1}"
            ),
            expedition_yaml=EXPEDITION,
        )

        self._hash_to_json(
            problem,
            problem_hash,
            problem_waypoint_i,
            hash_path,
        )

        # check if enough contingency time has been scheduled to avoid delay affecting future waypoints
        with yaspin(text="Assessing impact on expedition schedule..."):
            time.sleep(5.0)

        has_contingency = self._has_contingency(problem, problem_waypoint_i)

        if has_contingency:
            print(LOG_MESSAGING["problem_avoided"])

            # update problem json to resolved = True
            with open(hash_path, encoding="utf-8") as f:
                problem_json = json.load(f)
            problem_json["resolved"] = True
            with open(hash_path, "w", encoding="utf-8") as f_out:
                json.dump(problem_json, f_out, indent=4)

            with yaspin():  # time to read message before simulation continues
                time.sleep(7.0)
            return

        else:
            affected = (
                "in-port"
                if problem_waypoint_i is None
                else f"at waypoint {problem_waypoint_i + 1}"
            )
            print(
                f"\nNot enough contingency time scheduled to mitigate delay of {problem.delay_duration.total_seconds() / 3600.0} hours occuring {affected} (future waypoint(s) would be reached too late).\n"
            )
            print(result_msg)

        # save checkpoint
        checkpoint = Checkpoint(
            past_schedule=self.expedition.schedule,
            failed_waypoint_i=problem_waypoint_i + 1
            if problem_waypoint_i is not None
            else 0,
        )  # failed waypoint index then becomes the one after the one where the problem occurred; as this is when scheduling issues would be run into; for pre-departure problems this is the first waypoint
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

    def _has_contingency(
        self,
        problem: InstrumentProblem | GeneralProblem,
        problem_waypoint_i: int | None,
    ) -> bool:
        """Determine if enough contingency time has been scheduled to avoid delay affecting the waypoint immediately after the problem."""
        if problem_waypoint_i is None:
            return False  # pre-departure problems always cause delay to first waypoint

        else:
            #! TODO: this still needs to incoporate the instrument deployment times as well!!

            delay_duration = problem.delay_duration.total_seconds() / 3600.0  # hours
            curr_wp = self.expedition.schedule.waypoints[problem_waypoint_i]
            next_wp = self.expedition.schedule.waypoints[problem_waypoint_i + 1]

            scheduled_time_diff = (
                next_wp.time - curr_wp.time
            ).total_seconds() / 3600.0  # hours

            sail_time = (
                _calc_sail_time(
                    curr_wp.location,
                    next_wp.location,
                    ship_speed_knots=self.expedition.ship_config.ship_speed_knots,
                    projection=PROJECTION,
                )[0].total_seconds()
                / 3600.0
            )
            return scheduled_time_diff > sail_time + delay_duration

    def _make_checkpoint(self, failed_waypoint_i: int | None = None) -> Checkpoint:
        """Make checkpoint, also handling pre-departure."""
        return Checkpoint(
            past_schedule=self.expedition.schedule, failed_waypoint_i=failed_waypoint_i
        )

    def _make_hash(self, s: str, length: int) -> str:
        """Make unique hash for problem occurrence."""
        assert length % 2 == 0, "Length must be even."
        half_length = length // 2
        return hashlib.shake_128(s.encode("utf-8")).hexdigest(half_length)

    def _hash_to_json(
        self,
        problem: InstrumentProblem | GeneralProblem,
        problem_hash: str,
        problem_waypoint_i: int | None,
        hash_path: Path,
    ) -> dict:
        """Convert problem details + hash to json."""
        os.makedirs(self.expedition_dir / PROBLEMS_ENCOUNTERED_DIR, exist_ok=True)
        hash_data = {
            "problem_hash": problem_hash,
            "message": problem.message,
            "problem_waypoint_i": problem_waypoint_i,
            "delay_duration_hours": problem.delay_duration.total_seconds() / 3600.0,
            "timestamp": time.strftime("%Y-%m-%d %H:%M:%S", time.localtime()),
            "resolved": False,
        }
        with open(hash_path, "w", encoding="utf-8") as f:
            json.dump(hash_data, f, indent=4)

    def _cache_original_schedule(self, schedule: Schedule, path: Path | str):
        """Cache original schedule to file for reference, as a checkpoint object."""
        schedule_original = Checkpoint(past_schedule=schedule)
        schedule_original.to_yaml(path)
        print(f"\nOriginal schedule cached to {path}.\n")
