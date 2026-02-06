from __future__ import annotations

import json
import os
import random
import sys
import time
from pathlib import Path
from typing import TYPE_CHECKING

from rich import box
from rich.console import Console
from rich.live import Live
from rich.spinner import Spinner
from rich.table import Table
from yaspin import yaspin

from virtualship.instruments.types import InstrumentType
from virtualship.make_realistic.problems.scenarios import (
    GeneralProblem,
    InstrumentProblem,
)
from virtualship.models.checkpoint import Checkpoint
from virtualship.utils import (
    EXPEDITION,
    GENERAL_PROBLEM_REG,
    INSTRUMENT_PROBLEM_REG,
    PROJECTION,
    SCHEDULE_ORIGINAL,
    _calc_sail_time,
    _calc_wp_stationkeeping_time,
    _make_hash,
    _save_checkpoint,
)

if TYPE_CHECKING:
    from virtualship.models.expedition import Expedition, Schedule

LOG_MESSAGING = {
    "pre_departure": "Hang on! There could be a pre-departure problem in-port...",
    "during_expedition": "Oh no, a problem has occurred during the expedition, at waypoint {waypoint}...!",
    "schedule_problems": "This problem will cause a delay of {delay_duration} hours {problem_wp}. The next waypoint therefore cannot be reached in time. Please account for this in your schedule (`virtualship plan` or directly in {expedition_yaml}), then continue the expedition by executing the `virtualship run` command again.\n",
    "problem_avoided": "Phew! You had enough contingency time scheduled to avoid delays from this problem.\n",
}


# default problem weights for problems simulator (i.e. add +1 problem for every n days/waypoints/instruments in expedition)
PROBLEM_WEIGHTS = {
    "every_ndays": 7,
    "every_nwaypoints": 6,
    "every_ninstruments": 3,
}


class ProblemSimulator:
    """Handle problem simulation during expedition."""

    def __init__(self, expedition: Expedition, expedition_dir: str | Path):
        """Initialise ProblemSimulator with a schedule and probability level."""
        self.expedition = expedition
        self.expedition_dir = Path(expedition_dir)

    def select_problems(
        self,
        instruments_in_expedition: set[InstrumentType],
        prob_level: int,
    ) -> dict[str, list[GeneralProblem | InstrumentProblem] | None] | None:
        """
        Select problems (general and instrument-specific). When prob_level = 2, number of problems is determined by expedition length, instrument count etc.

        If only one waypoint, return just a pre-departure problem.

        Map each selected problem to a random waypoint (or None if pre-departure). Finally, cache the suite of problems to a directory (expedition-specific via hash) for reference.
        """
        valid_instrument_problems = [
            problem
            for problem in INSTRUMENT_PROBLEM_REG
            if problem.instrument_type in instruments_in_expedition
        ]

        pre_departure_problems = [
            p
            for p in GENERAL_PROBLEM_REG
            if issubclass(p, GeneralProblem) and p.pre_departure
        ]

        num_waypoints = len(self.expedition.schedule.waypoints)
        num_instruments = len(instruments_in_expedition)
        expedition_duration_days = (
            self.expedition.schedule.waypoints[-1].time
            - self.expedition.schedule.waypoints[0].time
        ).days

        # if only one waypoint, return just a pre-departure problem
        if num_waypoints < 2:
            return {
                "problem_class": [random.choice(pre_departure_problems)],
                "waypoint_i": [None],
            }

        if prob_level == 0:
            num_problems = 0
        elif prob_level == 1:
            num_problems = random.randint(1, 2)
        elif prob_level == 2:
            base = 1
            extra = (  # i.e. +1 problem for every n days/waypoints/instruments (tunable above)
                (expedition_duration_days // PROBLEM_WEIGHTS["every_ndays"])
                + (num_waypoints // PROBLEM_WEIGHTS["every_nwaypoints"])
                + (num_instruments // PROBLEM_WEIGHTS["every_ninstruments"])
            )
            num_problems = base + extra
            num_problems = min(
                num_problems, len(GENERAL_PROBLEM_REG) + len(valid_instrument_problems)
            )

        selected_problems = []
        problems_sorted = None
        if num_problems > 0:
            random.shuffle(GENERAL_PROBLEM_REG)
            random.shuffle(valid_instrument_problems)

            # bias towards more instrument problems when there are more instruments
            instrument_bias = min(0.7, num_instruments / (num_instruments + 2))
            n_instrument = round(num_problems * instrument_bias)
            n_general = min(len(GENERAL_PROBLEM_REG), num_problems - n_instrument)
            n_instrument = (
                num_problems - n_general
            )  # recalc in case n_general was capped to len(GENERAL_PROBLEM_REG)

            selected_problems.extend(GENERAL_PROBLEM_REG[:n_general])
            selected_problems.extend(valid_instrument_problems[:n_instrument])

            # allow only one pre-departure problem to occur; replace any extras with non-pre-departure problems
            selected_pre_departure = [
                p
                for p in selected_problems
                if issubclass(p, GeneralProblem) and p.pre_departure
            ]
            if len(selected_pre_departure) > 1:
                to_keep = random.choice(selected_pre_departure)
                num_to_replace = len(selected_pre_departure) - 1
                # remove all but one pre_departure problem
                selected_problems = [
                    problem
                    for problem in selected_problems
                    if not (
                        issubclass(problem, GeneralProblem)
                        and problem.pre_departure
                        and problem is not to_keep
                    )
                ]
                # available non-pre_departure problems not already selected
                available_general = [
                    p
                    for p in GENERAL_PROBLEM_REG
                    if not p.pre_departure and p not in selected_problems
                ]
                available_instrument = [
                    p for p in valid_instrument_problems if p not in selected_problems
                ]
                available_replacements = available_general + available_instrument
                random.shuffle(available_replacements)
                selected_problems.extend(available_replacements[:num_to_replace])

            # map each problem to a [random] waypoint (or None if pre-departure)
            waypoint_idxs = []
            for problem in selected_problems:
                if getattr(problem, "pre_departure", False):
                    waypoint_idxs.append(None)
                else:
                    # TODO: if incorporate departure and arrival port/waypoints in future, bear in mind index selection here may need to change
                    waypoint_idxs.append(
                        random.randint(0, len(self.expedition.schedule.waypoints) - 2)
                    )  # -1 to get index and -1 exclude last waypoint (would not impact any future scheduling as arrival in port is not part of schedule)

            # pair problems with their waypoint indices and sort by waypoint index (pre-departure first)
            paired = sorted(
                zip(selected_problems, waypoint_idxs, strict=True),
                key=lambda x: (x[1] is not None, x[1] if x[1] is not None else -1),
            )
            problems_sorted = {
                "problem_class": [p for p, _ in paired],
                "waypoint_i": [w for _, w in paired],
            }

        return problems_sorted if selected_problems else None

    def execute(
        self,
        problems: dict[str, list[GeneralProblem | InstrumentProblem] | None],
        instrument_type_validation: InstrumentType | None,
        log_dir: Path,
        log_delay: float = 4.0,
    ):
        """
        Execute the selected problems, returning messaging and delay times.

        N.B. a problem_waypoint_i is different to a failed_waypoint_i defined in the Checkpoint class; failed_waypoint_i is the waypoint index after the problem_waypoint_i where the problem occurred, as this is when scheduling issues would be encountered.
        """
        for problem, problem_waypoint_i in zip(
            problems["problem_class"], problems["waypoint_i"], strict=True
        ):
            # skip if instrument problem but `p.instrument_type` does not match `instrument_type_validation` (i.e. the current instrument being simulated in the expedition, e.g. from _run.py)
            if (
                issubclass(problem, InstrumentProblem)
                and problem.instrument_type is not instrument_type_validation
            ):
                continue

            problem_hash = _make_hash(problem.message + str(problem_waypoint_i), 8)
            hash_fpath = log_dir.joinpath(f"problem_{problem_hash}.json")
            if hash_fpath.exists():
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
                hash_fpath,
                log_delay,
            )

            # cache original schedule for reference and/or restoring later if needed (checkpoint.yaml [written in _log_problem] can be overwritten if multiple problems occur so is not a persistent record of original schedule)
            schedule_original_fpath = log_dir / SCHEDULE_ORIGINAL
            if not os.path.exists(schedule_original_fpath):
                self._cache_original_schedule(
                    self.expedition.schedule, schedule_original_fpath
                )

    @staticmethod
    def cache_selected_problems(
        problems: dict[str, list[GeneralProblem | InstrumentProblem] | None],
        selected_problems_fpath: str,
    ) -> None:
        """Cache suite of problems to json, for reference."""
        # make dir to contain problem jsons (unique to expedition)
        os.makedirs(Path(selected_problems_fpath).parent, exist_ok=True)

        # cache dict of selected_problems to json
        with open(
            selected_problems_fpath,
            "w",
            encoding="utf-8",
        ) as f:
            json.dump(
                {
                    "problem_class": [p.__name__ for p in problems["problem_class"]],
                    "waypoint_i": problems["waypoint_i"],
                    "timestamp": time.strftime("%Y-%m-%d %H:%M:%S", time.localtime()),
                },
                f,
                indent=4,
            )

    @staticmethod
    def post_expedition_report(
        problems: dict[str, list[GeneralProblem | InstrumentProblem] | None],
        report_fpath: str | Path,
    ) -> None:
        """Produce human-readable post-expedition report (.txt), including problems that occured (their full messages), the waypoint and what delay they caused."""
        for problem, problem_waypoint_i in zip(
            problems["problem_class"], problems["waypoint_i"], strict=True
        ):
            affected_wp = (
                "in-port" if problem_waypoint_i is None else f"{problem_waypoint_i + 1}"
            )
            delay_hours = problem.delay_duration.total_seconds() / 3600.0
            with open(report_fpath, "a", encoding="utf-8") as f:
                f.write("---\n")
                f.write(f"Waypoint: {affected_wp}\n")
                f.write(f"Problem: {problem.message}\n")
                f.write(f"Delay caused: {delay_hours} hours\n\n")

    @staticmethod
    def load_selected_problems(
        selected_problems_fpath: str,
    ) -> dict[str, list[GeneralProblem | InstrumentProblem] | None]:
        """Load previously selected problem classes from json."""
        with open(
            selected_problems_fpath,
            encoding="utf-8",
        ) as f:
            problems_json = json.load(f)

        # extract selected problem classes from their names (using the lookups preserves order they were saved in)
        selected_problems = {"problem_class": [], "waypoint_i": []}
        general_problems_lookup = {cls.__name__: cls for cls in GENERAL_PROBLEM_REG}
        instrument_problems_lookup = {
            cls.__name__: cls for cls in INSTRUMENT_PROBLEM_REG
        }

        for cls_name, wp_idx in zip(
            problems_json["problem_class"], problems_json["waypoint_i"], strict=True
        ):
            if cls_name in general_problems_lookup:
                selected_problems["problem_class"].append(
                    general_problems_lookup[cls_name]
                )
            elif cls_name in instrument_problems_lookup:
                selected_problems["problem_class"].append(
                    instrument_problems_lookup[cls_name]
                )
            else:
                raise ValueError(
                    f"Problem class '{cls_name}' not found in known problem registries."
                )
            selected_problems["waypoint_i"].append(wp_idx)

        return selected_problems

    def _log_problem(
        self,
        problem: GeneralProblem | InstrumentProblem,
        problem_waypoint_i: int | None,
        alert_msg: str,
        problem_hash: str,
        hash_fpath: Path,
        log_delay: float,
    ):
        """Log problem occurrence with spinner and delay, save to checkpoint, write hash."""
        time.sleep(3.0)  # brief pause before spinner
        with yaspin(text=alert_msg) as spinner:
            time.sleep(log_delay)
            spinner.ok("💥 ")

        self._hash_to_json(
            problem,
            problem_hash,
            problem_waypoint_i,
            hash_fpath,
        )

        has_contingency = self._has_contingency(problem, problem_waypoint_i)

        if has_contingency:
            impact_str = LOG_MESSAGING["problem_avoided"]
            result_str = "The expedition will carry on shortly as planned."

            # update problem json to resolved = True
            with open(hash_fpath, encoding="utf-8") as f:
                problem_json = json.load(f)
            problem_json["resolved"] = True
            with open(hash_fpath, "w", encoding="utf-8") as f_out:
                json.dump(problem_json, f_out, indent=4)

        else:
            affected = (
                "in-port"
                if problem_waypoint_i is None
                else f"at waypoint {problem_waypoint_i + 1}"
            )

            impact_str = f"Not enough contingency time scheduled to mitigate delay of {problem.delay_duration.total_seconds() / 3600.0} hours occuring {affected} (future waypoint(s) would be reached too late).\n"
            result_str = LOG_MESSAGING["schedule_problems"].format(
                delay_duration=problem.delay_duration.total_seconds() / 3600.0,
                problem_wp=affected,
                expedition_yaml=EXPEDITION,
            )

        # save checkpoint
        checkpoint = Checkpoint(
            past_schedule=self.expedition.schedule,
            failed_waypoint_i=problem_waypoint_i + 1
            if problem_waypoint_i is not None
            else 0,
        )  # failed waypoint index then becomes the one after the one where the problem occurred; as this is when scheduling issues would be run into; for pre-departure problems this is the first waypoint
        _save_checkpoint(checkpoint, self.expedition_dir)

        # display tabular output in
        self._tabular_outputter(
            problem_str=problem.message,
            impact_str=impact_str,
            result_str=result_str,
            has_contingency=has_contingency,
        )

        if has_contingency:
            return  # continue expedition as normal
        else:
            sys.exit(0)  # pause simulation

    def _has_contingency(
        self,
        problem: InstrumentProblem | GeneralProblem,
        problem_waypoint_i: int | None,
    ) -> bool:
        """Determine if enough contingency time has been scheduled to avoid delay affecting the waypoint immediately after the problem."""
        if problem_waypoint_i is None:
            return False  # pre-departure problems always cause delay to first waypoint

        else:
            curr_wp = self.expedition.schedule.waypoints[problem_waypoint_i]
            next_wp = self.expedition.schedule.waypoints[problem_waypoint_i + 1]

            wp_stationkeeping_time = _calc_wp_stationkeeping_time(
                curr_wp.instrument, self.expedition
            )

            scheduled_time_diff = next_wp.time - curr_wp.time

            sail_time = _calc_sail_time(
                curr_wp.location,
                next_wp.location,
                ship_speed_knots=self.expedition.ship_config.ship_speed_knots,
                projection=PROJECTION,
            )[0]

            return (
                scheduled_time_diff
                > sail_time + wp_stationkeeping_time + problem.delay_duration
            )

    def _make_checkpoint(self, failed_waypoint_i: int | None = None) -> Checkpoint:
        """Make checkpoint, also handling pre-departure."""
        return Checkpoint(
            past_schedule=self.expedition.schedule, failed_waypoint_i=failed_waypoint_i
        )

    @staticmethod
    def _hash_to_json(
        problem: InstrumentProblem | GeneralProblem,
        problem_hash: str,
        problem_waypoint_i: int | None,
        hash_path: Path,
    ) -> dict:
        """Convert problem details + hash to json."""
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

    @staticmethod
    def _cache_original_schedule(schedule: Schedule, path: Path | str):
        """Cache original schedule to file for reference, as a checkpoint object."""
        schedule_original = Checkpoint(past_schedule=schedule)
        schedule_original.to_yaml(path)
        print(f"\nOriginal schedule cached to {path}.\n")

    @staticmethod
    def _tabular_outputter(problem_str, impact_str, result_str, has_contingency: bool):
        """Display the problem, impact, and result in a live-updating table. Sleep times are included to increase readability and engagement for user."""
        console = Console()
        console.print()  # line break before table

        col_kwargs = dict(ratio=1, no_wrap=False, max_width=None, justify="left")

        def make_table(problem, impact, result, col_kwargs, colour_results=False):
            table = Table(box=box.SIMPLE, expand=True)
            table.add_column("Problem Encountered", **col_kwargs)
            table.add_column("Impact on schedule", **col_kwargs)

            if colour_results:
                style = "green1" if has_contingency else "red1"
                table.add_column("Result", style=style, **col_kwargs)
            else:
                table.add_column("Result", **col_kwargs)

            table.add_row(problem, impact, result)
            return table

        empty_spinner = Spinner("dots", text="")
        impact_spinner = Spinner("dots", text="Assessing impact on schedule...")

        with Live(console=console, refresh_per_second=10) as live:
            # stage 0: empty table
            table = make_table(empty_spinner, empty_spinner, empty_spinner, col_kwargs)
            live.update(table)
            time.sleep(3.0)

            # stage 1: show problem
            table = make_table(problem_str, empty_spinner, empty_spinner, col_kwargs)
            live.update(table)
            time.sleep(3.0)

            # stage 2: spinner in "Impact on schedule" column
            table = make_table(problem_str, impact_spinner, empty_spinner, col_kwargs)
            live.update(table)
            time.sleep(7.0)

            # stage 3: table with problem and impact-investigation complete
            table = make_table(problem_str, impact_str, empty_spinner, col_kwargs)
            live.update(table)
            time.sleep(4.0)

            # stage 4: complete table with problem, impact, and result (give final outcome colour based on fail/success)
            table = make_table(
                problem_str, impact_str, result_str, col_kwargs, colour_results=True
            )
            live.update(table)
            time.sleep(3.0)
