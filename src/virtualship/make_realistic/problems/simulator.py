from __future__ import annotations

import json
import random
import sys
import time
from datetime import timedelta
from pathlib import Path
from typing import TYPE_CHECKING, Any

from rich import box
from rich.console import Console
from rich.live import Live
from rich.spinner import Spinner
from rich.table import Table
from yaspin import yaspin

from virtualship.instruments.types import InstrumentType
from virtualship.make_realistic.problems.scenarios import (
    GENERAL_PROBLEMS,
    INSTRUMENT_PROBLEMS,
    GeneralProblem,
    InstrumentProblem,
)
from virtualship.models.checkpoint import Checkpoint
from virtualship.models.expedition import Port
from virtualship.utils import (
    CACHE,
    EXPEDITION,
    EXPEDITION_LATEST,
    EXPEDITION_ORIGINAL,
    PROJECTION,
    _calc_sail_time,
    _calc_wp_stationkeeping_time,
    _get_public_wp,
    _make_hash,
    _save_checkpoint,
)

if TYPE_CHECKING:
    from virtualship.models.expedition import Expedition

LOG_MESSAGING = {
    "pre_departure": "Hang on! There could be a pre-departure problem in-port...",
    "during_expedition": "Oh no, a problem has occurred during the expedition, at waypoint {waypoint}...!",
    "schedule_problems": (
        "This problem will cause a delay of {delay_duration} hours {problem_wp}. "
        "The next waypoint therefore cannot be reached in time. Please account for this "
        "in your schedule (`virtualship plan` or directly in {expedition_yaml}), then continue "
        "the expedition by executing the `virtualship run` command again.\n"
    ),
    "problem_avoided": "Phew! You had enough contingency time scheduled to avoid delays from this problem.\n",
}

# default problem weights for problems simulator (e.g., +1 problem every N days/waypoints/instruments)
PROBLEM_WEIGHTS = {
    "every_ndays": 7,
    "every_nwaypoints": 6,
    "every_ninstruments": 3,
}

ProblemType = GeneralProblem | InstrumentProblem
SelectedProblemsDict = dict[str, list[ProblemType | None]]


class ProblemSimulator:
    """Handle problem simulation during an expedition."""

    def __init__(self, expedition: Expedition, expedition_dir: str | Path):
        """Initialise ProblemSimulator with a schedule and probability level."""
        self.expedition = expedition
        self.expedition_dir = Path(expedition_dir)

        self.waypoints = expedition.schedule.waypoints

    def __post_init__(self):
        """Ensure first and last waypoints are Ports. Allows the problem selection to work properly."""
        assert isinstance(self.waypoints[0], Port) & isinstance(
            self.waypoints[-1], Port
        ), "First and last waypoints must be Port types."

    def select_problems(
        self,
        instruments_in_expedition: set[InstrumentType],
        difficulty_level: str,
    ) -> SelectedProblemsDict | None:
        """
        Select problems (general and instrument-specific). When difficulty_level = 'hard', number of problems is determined by expedition length, instrument count etc.

        If only one waypoint, return just a pre-departure problem.

        Map each selected problem to a random waypoint (or 0th [i.e. departure port] if pre-departure). Finally, cache the suite of problems to a directory (expedition-specific) for reference.
        """
        # handle early-exit single waypoint case (pre-departure only)
        if len(self.waypoints) < 2:
            pre_departure = [p for p in GENERAL_PROBLEMS if p.pre_departure]
            return {
                "problem_class": [random.choice(pre_departure)],
                "waypoint_i": [0],  # noqa; pre-departure problem is always associated with the departure port (index 0)
            }

        valid_instruments = [
            p
            for p in INSTRUMENT_PROBLEMS
            if p.instrument_type in instruments_in_expedition
        ]
        num_problems = self._calculate_problem_count(
            difficulty_level=difficulty_level,
            expedition_days=(self.waypoints[-1].time - self.waypoints[0].time).days,
            num_waypoints=len(self.waypoints),
            num_instruments=len(instruments_in_expedition),
            max_available=len(GENERAL_PROBLEMS) + len(valid_instruments),
        )

        if num_problems <= 0:
            return None

        selected = self._sample_problems(
            num_problems, valid_instruments, len(instruments_in_expedition)
        )
        selected = self._limit_pre_departure(selected, valid_instruments)

        return self._assign_problems_to_waypoints(selected)

    def _calculate_problem_count(
        self,
        difficulty_level: str,
        expedition_days: int,
        num_waypoints: int,
        num_instruments: int,
        max_available: int,
    ) -> int:
        """Determine problem count based on difficulty setting."""
        if difficulty_level == "easy":
            return 0
        if difficulty_level == "medium":
            return random.randint(1, 2)
        if difficulty_level == "hard":
            extra = (
                (expedition_days // PROBLEM_WEIGHTS["every_ndays"])
                + (num_waypoints // PROBLEM_WEIGHTS["every_nwaypoints"])
                + (num_instruments // PROBLEM_WEIGHTS["every_ninstruments"])
            )
            return min(1 + extra, max_available)
        return 0

    def _sample_problems(
        self,
        num_problems: int,
        valid_instruments: list[InstrumentProblem],
        num_instruments: int,
    ) -> list[ProblemType]:
        """Sample a balanced ratio of general and instrument problems."""
        general_pool = list(GENERAL_PROBLEMS)
        instrument_pool = list(valid_instruments)
        random.shuffle(general_pool)
        random.shuffle(instrument_pool)

        bias = min(0.7, num_instruments / (num_instruments + 2))
        n_inst = round(num_problems * bias)
        n_gen = min(len(general_pool), num_problems - n_inst)
        n_inst = num_problems - n_gen  # noqa; recalc in case n_gen was capped to len(GENERAL_PROBLEMS)

        return general_pool[:n_gen] + instrument_pool[:n_inst]

    def _limit_pre_departure(
        self,
        selected: list[ProblemType],
        valid_instruments: list[InstrumentProblem],
    ) -> list[ProblemType]:
        """Ensure maximum of one pre-departure problem is selected."""
        pre_deps = [
            p for p in selected if isinstance(p, GeneralProblem) and p.pre_departure
        ]
        if len(pre_deps) <= 1:
            return selected

        keep = random.choice(pre_deps)
        replacements_needed = len(pre_deps) - 1
        filtered = [
            p for p in selected if p is keep or not getattr(p, "pre_departure", False)
        ]

        avail_gen = [
            p for p in GENERAL_PROBLEMS if not p.pre_departure and p not in filtered
        ]
        avail_inst = [p for p in valid_instruments if p not in filtered]
        replacements = avail_gen + avail_inst
        random.shuffle(replacements)

        return filtered + replacements[:replacements_needed]

    def _assign_problems_to_waypoints(
        self, selected: list[ProblemType]
    ) -> SelectedProblemsDict | None:
        """Assign sampled problems to valid, non-port waypoint indices."""
        waypoints = self.waypoints
        avail_indices = [
            i for i, wp in enumerate(waypoints) if not isinstance(wp, Port)
        ]
        random.shuffle(avail_indices)

        assert 0 not in avail_indices, (
            "Index 0 (departure port) should not be in available waypoint indices for non-pre-departure problems."
        )

        assigned_problems: list[ProblemType] = []
        assigned_indices: list[int | None] = []

        for problem in selected:
            if getattr(problem, "pre_departure", False):
                assigned_problems.append(problem)
                assigned_indices.append(0)  # noqa; pre-departure problem is always associated with the departure port (index 0)
                continue

            if not avail_indices:
                break

            # find matching waypoint or substitute with general problem
            target_idx = None
            for idx in avail_indices:
                wp_instruments = waypoints[idx].instrument or []
                if (
                    isinstance(problem, InstrumentProblem)
                    and problem.instrument_type not in wp_instruments
                ):
                    continue
                target_idx = idx
                break

            if target_idx is not None:
                avail_indices.remove(target_idx)
                assigned_problems.append(problem)
                assigned_indices.append(target_idx)
            else:
                # fall back to a general problem if instrument match fails
                avail_general = [
                    p
                    for p in GENERAL_PROBLEMS
                    if not p.pre_departure and p not in assigned_problems
                ]
                if avail_general and avail_indices:
                    substitute = random.choice(avail_general)
                    assigned_problems.append(substitute)
                    assigned_indices.append(avail_indices.pop())

        if not assigned_problems:
            return None

        # sort chronologically (waypoint 0 first, then remaining waypoint index order)
        paired = sorted(
            zip(assigned_problems, assigned_indices, strict=True),
            key=lambda x: 0 if x[1] == 0 else x[1],
        )
        return {
            "problem_class": [p for p, _ in paired],
            "waypoint_i": [w for _, w in paired],
        }

    def execute(
        self,
        problems: SelectedProblemsDict,
        instrument_type_validation: InstrumentType | None,
        log_dir: Path,
        log_delay: float = 4.0,
    ) -> None:
        """Execute simulation problems and apply delay/schedule impacts."""
        for problem, wp_i in zip(
            problems["problem_class"], problems["waypoint_i"], strict=True
        ):
            if (
                isinstance(problem, InstrumentProblem)
                and problem.instrument_type is not instrument_type_validation
            ):
                continue

            problem_hash = _make_hash(problem.message + str(wp_i), 8)
            hash_fpath = log_dir / f"problem_{problem_hash}.json"
            if hash_fpath.exists():
                continue

            self._log_problem(problem, wp_i, problem_hash, hash_fpath, log_delay)
            self._cache_original_expedition(self.expedition)

    def _log_problem(
        self,
        problem: ProblemType,
        problem_wp_i: int | None,
        problem_hash: str,
        hash_fpath: Path,
        log_delay: float,
    ) -> None:
        """
        Handle execution sequence, logging, checkpoint saving, and user presentation.

        Note, problem_wp_i is the index of the waypoint in the expedition schedule, but the user-facing message should be based on the index of the waypoint in the list of non-port waypoints.
        Use problem_wp_i for internal logic, but user-facing messages (below) should use public_wp (non indexed version).
        problem_wp_i will often == public_wp (given 0-indexing), but this makes the logic explicit and clear.
        """
        waypoints = self.waypoints
        public_wp = _get_public_wp(problem_wp_i, waypoints)

        alert_msg = (
            LOG_MESSAGING["pre_departure"]
            if isinstance(problem, GeneralProblem) and problem.pre_departure
            else LOG_MESSAGING["during_expedition"].format(waypoint=public_wp)
        )

        time.sleep(3.0)
        with yaspin(text=alert_msg) as spinner:
            time.sleep(log_delay)
            spinner.ok("💥 ")

        self._hash_to_json(problem, problem_hash, problem_wp_i, hash_fpath)
        has_contingency = self._has_contingency(problem, problem_wp_i)
        delay_hrs = problem.delay_duration.total_seconds() / 3600.0

        if has_contingency:
            impact_str = LOG_MESSAGING["problem_avoided"]
            result_str = "The expedition will carry on shortly as planned."
            # update problem JSON state to resolved
            data = self._read_json(hash_fpath)
            data["resolved"] = True
            self._write_json(hash_fpath, data)
        else:
            affected = "in-port" if public_wp is None else f"at waypoint {public_wp}"
            impact_str = (
                f"Not enough contingency time scheduled to mitigate delay of {delay_hrs} "
                f"hours occurring {affected} (future waypoint(s) would be reached too late).\n"
            )
            result_str = LOG_MESSAGING["schedule_problems"].format(
                delay_duration=delay_hrs,
                problem_wp=affected,
                expedition_yaml=EXPEDITION,
            )

        # update and save checkpoints
        checkpoint = Checkpoint(
            past_schedule=self.expedition.schedule,
            problem_wp_i=problem_wp_i,
        )
        _save_checkpoint(checkpoint, self.expedition_dir)
        self.expedition.to_yaml(self.expedition_dir / CACHE / EXPEDITION_LATEST)

        self._tabular_outputter(
            problem_str=problem.message,
            impact_str=impact_str,
            result_str=result_str,
            has_contingency=has_contingency,
        )

        if not has_contingency:
            sys.exit(0)

    def _has_contingency(self, problem: ProblemType, problem_wp_i: int | None) -> bool:
        """Check whether scheduled contingency covers expected delay duration."""
        curr_wp, next_wp = (
            self.waypoints[problem_wp_i],
            self.waypoints[problem_wp_i + 1],
        )

        stationkeeping = (
            _calc_wp_stationkeeping_time(curr_wp.instrument, self.expedition)
            if not isinstance(curr_wp, Port)
            else timedelta(0)
        )
        sail_time = _calc_sail_time(
            curr_wp.location,
            next_wp.location,
            ship_speed_knots=self.expedition.ship_config.ship_speed_knots,
            projection=PROJECTION,
        )[0]

        scheduled_time = next_wp.time - curr_wp.time
        required_time = sail_time + stationkeeping + problem.delay_duration

        return scheduled_time > required_time

    def _cache_original_expedition(self, expedition: Expedition) -> None:
        """Cache original schedule configuration to file for recovery."""
        path = self.expedition_dir / CACHE / EXPEDITION_ORIGINAL
        if not path.exists():
            expedition.to_yaml(path)
            print(f"\nOriginal expedition.yaml cached to {path}.\n")

    @staticmethod
    def cache_selected_problems(
        problems: SelectedProblemsDict, selected_problems_fpath: str | Path
    ) -> None:
        """Cache suite of selected problems to JSON."""
        fpath = Path(selected_problems_fpath)
        fpath.parent.mkdir(parents=True, exist_ok=True)

        payload = {
            "problem_class": [p.short_name for p in problems["problem_class"]],
            "waypoint_i": problems["waypoint_i"],
            "timestamp": time.strftime("%Y-%m-%d %H:%M:%S", time.localtime()),
        }
        ProblemSimulator._write_json(fpath, payload)

    @staticmethod
    def load_selected_problems(
        selected_problems_fpath: str | Path,
    ) -> SelectedProblemsDict:
        """Load selected problems suite from a cached JSON file."""
        data = ProblemSimulator._read_json(Path(selected_problems_fpath))

        general_lookup = {cls.short_name: cls for cls in GENERAL_PROBLEMS}
        instrument_lookup = {cls.short_name: cls for cls in INSTRUMENT_PROBLEMS}

        selected_classes, waypoint_indices = [], []
        for cls_name, wp_idx in zip(
            data["problem_class"], data["waypoint_i"], strict=True
        ):
            if cls_name in general_lookup:
                selected_classes.append(general_lookup[cls_name])
            elif cls_name in instrument_lookup:
                selected_classes.append(instrument_lookup[cls_name])
            else:
                raise ValueError(
                    f"Problem class '{cls_name}' not found in known registries."
                )
            waypoint_indices.append(wp_idx)

        return {"problem_class": selected_classes, "waypoint_i": waypoint_indices}

    @staticmethod
    def post_expedition_report(
        problems: SelectedProblemsDict, report_fpath: str | Path
    ) -> None:
        """Append human-readable report summary of all occurring problems."""
        with open(report_fpath, "a", encoding="utf-8") as f:
            for problem, wp_i in zip(
                problems["problem_class"], problems["waypoint_i"], strict=True
            ):
                affected = "in-port" if wp_i is None else f"{wp_i + 1}"
                delay_hrs = problem.delay_duration.total_seconds() / 3600.0
                f.write(
                    f"---\nWaypoint: {affected}\n"
                    f"Problem: {problem.message}\n"
                    f"Delay caused: {delay_hrs} hours\n\n"
                )

    @staticmethod
    def _hash_to_json(
        problem: ProblemType,
        problem_hash: str,
        problem_wp_i: int | None,
        hash_path: Path,
    ) -> None:
        """Serialize runtime problem detail to JSON."""
        hash_data = {
            "problem_hash": problem_hash,
            "message": problem.message,
            "problem_wp_i": problem_wp_i,
            "delay_duration_hours": problem.delay_duration.total_seconds() / 3600.0,
            "timestamp": time.strftime("%Y-%m-%d %H:%M:%S", time.localtime()),
            "resolved": False,
        }
        ProblemSimulator._write_json(hash_path, hash_data)

    @staticmethod
    def _read_json(path: Path) -> dict[str, Any]:
        with open(path, encoding="utf-8") as f:
            return json.load(f)

    @staticmethod
    def _write_json(path: Path, data: dict[str, Any]) -> None:
        with open(path, "w", encoding="utf-8") as f:
            json.dump(data, f, indent=4)

    @staticmethod
    def _tabular_outputter(
        problem_str: str, impact_str: str, result_str: str, has_contingency: bool
    ) -> None:
        """Display the problem, impact, and result in a live-updating table. Sleep times are included to increase readability and engagement for user."""
        console = Console()
        console.print()  # line break before table

        col_kwargs = dict(ratio=1, no_wrap=False, justify="left")

        def make_table(problem, impact, result, colour_results=False) -> Table:
            table = Table(box=box.SIMPLE, expand=True)
            table.add_column("Problem Encountered", **col_kwargs)
            table.add_column("Impact on schedule", **col_kwargs)

            style = (
                ("green1" if has_contingency else "red1") if colour_results else None
            )
            table.add_column("Result", style=style, **col_kwargs)
            table.add_row(problem, impact, result)
            return table

        empty = Spinner("dots", text="")
        impact_spinner = Spinner("dots", text="Assessing impact on schedule...")

        stages = [
            (empty, empty, empty, False, 3.0),
            (problem_str, empty, empty, False, 3.0),
            (problem_str, impact_spinner, empty, False, 7.0),
            (problem_str, impact_str, empty, False, 4.0),
            (problem_str, impact_str, result_str, True, 3.0),
        ]

        with Live(console=console, refresh_per_second=10) as live:
            for prob, imp, res, colour, sleep_time in stages:
                live.update(make_table(prob, imp, res, colour_results=colour))
                time.sleep(sleep_time)
