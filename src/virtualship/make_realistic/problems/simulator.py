from __future__ import annotations

import datetime
import json
import random
import sys
import time
from collections.abc import Iterator
from dataclasses import dataclass, field
from datetime import datetime as dt
from pathlib import Path
from typing import TYPE_CHECKING, Any

from rich import box
from rich.console import Console
from rich.live import Live
from rich.spinner import Spinner
from rich.table import Table
from yaspin import yaspin

from virtualship.errors import CheckpointError
from virtualship.instruments.types import InstrumentType
from virtualship.make_realistic.problems.scenarios import (
    GENERAL_PROBLEMS,
    INSTRUMENT_PROBLEMS,
    GeneralProblem,
    InstrumentProblem,
)
from virtualship.models.checkpoint import ActiveProblem, Checkpoint
from virtualship.models.expedition import Port
from virtualship.utils import (
    CACHE,
    CHECKPOINT,
    EXPEDITION,
    EXPEDITION_IDENTIFIER,
    EXPEDITION_LATEST,
    EXPEDITION_ORIGINAL,
    PROBLEMS_ENCOUNTERED,
    PROJECTION,
    REPORT,
    RESULTS,
    SELECTED_PROBLEMS,
    _calc_sail_time,
    _calc_wp_stationkeeping_time,
    _get_public_wp,
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

PROBLEM_WEIGHTS = {
    "every_ndays": 7,
    "every_nwaypoints": 6,
    "every_ninstruments": 3,
}

ProblemType = GeneralProblem | InstrumentProblem


@dataclass
class ScheduledProblem:
    """Represents a single problem paired with its assigned waypoint index."""

    problem: ProblemType
    waypoint_index: int
    resolved: bool = False


@dataclass
class SelectedProblems:
    """Container holding scheduled problems for an expedition run."""

    items: list[ScheduledProblem] = field(default_factory=list)

    @property
    def is_fully_resolved(self) -> bool:
        """True if all scheduled problems are marked as resolved."""
        return bool(self.items) and all(item.resolved for item in self.items)

    @property
    def has_unresolved(self) -> bool:
        """True if there are remaining unresolved problems."""
        return any(not item.resolved for item in self.items)

    def mark_resolved(self, problem_message: str) -> None:
        """Mark a specific problem as resolved."""
        for item in self.items:
            if item.problem.message == problem_message:  # check is right problem
                item.resolved = True

    def __iter__(self) -> Iterator[ScheduledProblem]:
        """Iterate over scheduled problems."""
        return iter(self.items)

    def __len__(self) -> int:
        """Return the number of scheduled problems."""
        return len(self.items)


class ProblemSimulator:
    """Handle problem simulation during an expedition."""

    def __init__(
        self, expedition: Expedition, expedition_dir: str | Path, difficulty_level: str
    ):
        """Initialise ProblemSimulator with a schedule, dir and difficulty level."""
        self.expedition = expedition
        self.expedition_dir = Path(expedition_dir)
        self.expedition_id = self._unique_id()
        self.problems_dir = (
            self.expedition_dir
            / CACHE
            / PROBLEMS_ENCOUNTERED.format(expedition_id=self.expedition_id)
        )
        self.problems = self._load_or_select_problems(difficulty_level)

    @property
    def waypoints(self) -> list:
        """Convenience accessor for expedition schedule waypoints."""
        return self.expedition.schedule.waypoints

    def execute_for_instrument(self, instrument_type: InstrumentType) -> None:
        """Execute problems for a specific instrument type."""
        if not self.problems:
            return

        self.execute(
            self.problems,
            instrument_type_validation=instrument_type,
            log_dir=self.problems_dir,
        )

    def execute(
        self,
        problems: SelectedProblems,
        instrument_type_validation: InstrumentType | None,
        log_dir: Path,
        log_delay: float = 4.0,
    ) -> None:
        """Execute simulation problems and apply delay/schedule impacts."""
        if not problems or not problems.has_unresolved:
            return

        for item in problems:
            if item.resolved:
                continue

            problem = item.problem

            if (
                isinstance(problem, InstrumentProblem)
                and problem.instrument_type is not instrument_type_validation
            ):
                continue

            self._log_problem(item, log_delay)
            self._cache_original_expedition(self.expedition)

    def select_problems(
        self,
        instruments_in_expedition: set[InstrumentType],
        difficulty_level: str,
    ) -> SelectedProblems | None:
        """
        Select problems (general and instrument-specific). When difficulty_level = 'hard', number of problems is determined by expedition length, instrument count etc.

        If only one waypoint, return just a pre-departure problem.

        Map each selected problem to a random waypoint (or 0th [i.e. departure port] if pre-departure). Finally, cache the suite of problems to a directory (expedition-specific) for reference.
        """
        # handle early-exit single waypoint case (pre-departure only)
        if len(self.waypoints) < 2:
            pre_departure = [p for p in GENERAL_PROBLEMS if p.pre_departure]
            return SelectedProblems(
                items=[
                    ScheduledProblem(
                        problem=random.choice(pre_departure),
                        waypoint_index=0,  # pre-departure problem is always associated with the departure port (index 0)
                    )
                ]
            )

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

    def verify_problem_resolution(self, checkpoint: Checkpoint) -> None:
        """Verify active problem delay is resolved in new schedule."""
        active_problem = checkpoint.active_problem
        if active_problem is None or active_problem.resolved:
            return

        failed_wp_i = checkpoint.get_effective_failed_wp_i()
        new_schedule = self.expedition.schedule

        delay_duration = datetime.timedelta(hours=active_problem.delay_duration_hours)
        problem_waypoint = new_schedule.waypoints[checkpoint.problem_wp_i]
        failed_waypoint = new_schedule.waypoints[failed_wp_i]

        scheduled_time_diff = failed_waypoint.time - problem_waypoint.time
        stationkeeping_time = (
            _calc_wp_stationkeeping_time(problem_waypoint.instrument, self.expedition)
            if not isinstance(problem_waypoint, Port)
            else datetime.timedelta(0)
        )
        sail_time = _calc_sail_time(
            problem_waypoint.location,
            failed_waypoint.location,
            ship_speed_knots=self.expedition.ship_config.ship_speed_knots,
            projection=PROJECTION,
        )[0]

        min_time_required = sail_time + delay_duration + stationkeeping_time

        if scheduled_time_diff >= min_time_required:
            print("\n\n🎉 Previous problem has been resolved in the schedule.\n")
            active_problem.resolved = True
            _save_checkpoint(checkpoint, self.expedition_dir)

            problems_path = self.problems_dir / SELECTED_PROBLEMS
            if problems_path.exists():
                problems = self.load_selected_problems(problems_path)
                problems.mark_resolved(active_problem.message)
                self.cache_selected_problems(problems, problems_path)

        else:
            public_problem_wp = _get_public_wp(
                checkpoint.problem_wp_i, checkpoint.past_schedule.waypoints
            )
            public_failed_wp = _get_public_wp(
                failed_wp_i, checkpoint.past_schedule.waypoints
            )
            if public_failed_wp is None:
                public_failed_wp = "\b/Port of Arrival"

            problem_wp_str = (
                "in-port"
                if checkpoint.problem_wp_i == 0
                else f"at waypoint {public_problem_wp}"
            )
            time_elapsed = sail_time + delay_duration + stationkeeping_time

            raise CheckpointError(
                f"The problem encountered in previous simulation has not been resolved in the schedule! "
                f"Please adjust the schedule to account for delays caused by the problem...\n\n"
                f"The problem was associated with a delay duration of {active_problem.delay_duration_hours} hours {problem_wp_str} "
                f"(meaning waypoint {public_failed_wp} could not be reached in time). "
                f"Currently, the ship would reach waypoint {public_failed_wp} at {problem_waypoint.time + time_elapsed}, but the scheduled time is {failed_waypoint.time}."
            )

    def create_post_expedition_report(self) -> None:
        """Generate post-expedition report if any problems were selected."""
        if not self.problems:
            return

        report_path = self.expedition_dir / RESULTS / REPORT
        self.post_expedition_report(self.problems, report_path, self.waypoints)

        print("\n----- RECORD OF PROBLEMS ENCOUNTERED ------")
        print(
            f"\nA post-expedition report of problems encountered is saved in: {report_path}"
        )

    def _load_or_select_problems(
        self, difficulty_level: str
    ) -> SelectedProblems | None:
        """Load problems from JSON cache if available, otherwise select and cache new ones."""
        selected_problems_path = self.problems_dir / SELECTED_PROBLEMS
        if selected_problems_path.exists():
            return self.load_selected_problems(selected_problems_path)

        instruments = self.expedition.get_instruments()
        problems = self.select_problems(instruments, difficulty_level)
        if problems:
            self.cache_selected_problems(problems, selected_problems_path)
        return problems

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
    ) -> SelectedProblems | None:
        """Assign sampled problems to valid, non-port waypoint indices."""
        avail_indices = [
            i for i, wp in enumerate(self.waypoints) if not isinstance(wp, Port)
        ]
        random.shuffle(avail_indices)

        assigned: list[ScheduledProblem] = []

        for problem in selected:
            if getattr(problem, "pre_departure", False):
                assigned.append(
                    ScheduledProblem(
                        problem=problem,
                        waypoint_index=0,  # pre-departure problem is always associated with the departure port (index 0)
                    )
                )
                continue

            scheduled_item = self._match_problem_to_waypoint(
                problem, avail_indices, assigned
            )
            if scheduled_item:
                assigned.append(scheduled_item)

        if not assigned:
            return None

        assigned.sort(
            key=lambda x: 0 if x.waypoint_index == 0 else (x.waypoint_index or 0)
        )
        return SelectedProblems(items=assigned)

    def _match_problem_to_waypoint(
        self,
        problem: ProblemType,
        avail_indices: list[int],
        already_assigned: list[ScheduledProblem],
    ) -> ScheduledProblem | None:
        """Match a problem with an available waypoint or substitute with a general problem."""
        if not avail_indices:
            return None

        for idx in avail_indices:
            wp_instruments = self.waypoints[idx].instrument or []
            # discount problem if it's an instrument problem and the instrument isn't present at this waypoint
            if (
                isinstance(problem, InstrumentProblem)
                and problem.instrument_type not in wp_instruments
            ):
                continue

            avail_indices.remove(idx)
            return ScheduledProblem(problem=problem, waypoint_index=idx)

        used_problems = [item.problem for item in already_assigned]
        avail_general = [
            p
            for p in GENERAL_PROBLEMS
            if not p.pre_departure and p not in used_problems
        ]
        if avail_general and avail_indices:
            substitute = random.choice(avail_general)
            return ScheduledProblem(
                problem=substitute, waypoint_index=avail_indices.pop()
            )

        return None

    def _log_problem(
        self,
        item: ScheduledProblem,
        log_delay: float,
    ) -> None:
        """
        Handle execution sequence, logging, checkpoint saving, and user presentation.

        Note, problem_wp_i is the index of the waypoint in the expedition schedule, but the user-facing message
        should be based on the index of the waypoint in the list of non-port waypoints.
        Use problem_wp_i for internal logic, but user-facing messages should use public_wp.
        """
        problem = item.problem
        problem_wp_i = item.waypoint_index
        public_wp = _get_public_wp(problem_wp_i, self.waypoints)

        alert_msg = (
            LOG_MESSAGING["pre_departure"]
            if isinstance(problem, GeneralProblem) and problem.pre_departure
            else LOG_MESSAGING["during_expedition"].format(waypoint=public_wp)
        )

        time.sleep(3.0)
        with yaspin(text=alert_msg) as spinner:
            time.sleep(log_delay)
            spinner.ok("💥 ")

        has_contingency = self._has_contingency(problem, problem_wp_i)
        delay_hrs = problem.delay_duration.total_seconds() / 3600.0

        if has_contingency:
            impact_str = LOG_MESSAGING["problem_avoided"]
            result_str = "The expedition will carry on shortly as planned."
            active_problem = None

            # mark problem as resolved
            item.resolved = True
            if self.problems:
                self.cache_selected_problems(
                    self.problems, self.problems_dir / SELECTED_PROBLEMS
                )
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
            active_problem = ActiveProblem(
                message=problem.message,
                problem_wp_i=problem_wp_i,
                delay_duration_hours=delay_hrs,
                resolved=False,
            )

        checkpoint = Checkpoint(
            past_schedule=self.expedition.schedule,
            active_problem=active_problem,
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
        curr_wp = self.waypoints[problem_wp_i]
        next_wp = self.waypoints[problem_wp_i + 1]

        stationkeeping = (
            _calc_wp_stationkeeping_time(curr_wp.instrument, self.expedition)
            if not isinstance(curr_wp, Port)
            else datetime.timedelta(0)
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

    def _unique_id(self) -> str:
        """Resolve or generate the unique identifier for this expedition run."""
        cache_dir = self.expedition_dir / CACHE
        cache_dir.mkdir(exist_ok=True)

        id_path = cache_dir / EXPEDITION_IDENTIFIER
        last_expedition_path = cache_dir / EXPEDITION_LATEST
        checkpoint_path = self.expedition_dir / CHECKPOINT
        new_id = dt.now().strftime("%Y%m%d%H%M%S")

        if not id_path.exists():
            id_path.write_text(new_id)
            return new_id

        previous_id = id_path.read_text().strip()

        if checkpoint_path.exists():
            return previous_id

        if not last_expedition_path.exists():
            id_path.write_text(new_id)
            return new_id

        last_expedition = Expedition.from_yaml(last_expedition_path)
        added_instruments = set(self.expedition.get_instruments()) - set(
            last_expedition.get_instruments()
        )

        if added_instruments:
            id_path.write_text(new_id)
            return new_id

        return previous_id

    @staticmethod
    def cache_selected_problems(
        problems: SelectedProblems, selected_problems_fpath: str | Path
    ) -> None:
        """Cache suite of selected problems to JSON."""
        fpath = Path(selected_problems_fpath)
        fpath.parent.mkdir(parents=True, exist_ok=True)

        payload = {
            "problem_class": [item.problem.short_name for item in problems],
            "waypoint_i": [item.waypoint_index for item in problems],
            "resolved": [item.resolved for item in problems],
            "timestamp": time.strftime("%Y-%m-%d %H:%M:%S", time.localtime()),
        }
        ProblemSimulator._write_json(fpath, payload)

    @staticmethod
    def load_selected_problems(
        selected_problems_fpath: str | Path,
    ) -> SelectedProblems:
        """Load selected problems suite from a cached JSON file."""
        data = ProblemSimulator._read_json(Path(selected_problems_fpath))

        general_lookup = {cls.short_name: cls for cls in GENERAL_PROBLEMS}
        instrument_lookup = {cls.short_name: cls for cls in INSTRUMENT_PROBLEMS}

        resolved_list = data.get("resolved", [False] * len(data["problem_class"]))

        items = []
        for cls_name, wp_idx, is_res in zip(
            data["problem_class"], data["waypoint_i"], resolved_list, strict=True
        ):
            if cls_name in general_lookup:
                prob_cls = general_lookup[cls_name]
            elif cls_name in instrument_lookup:
                prob_cls = instrument_lookup[cls_name]
            else:
                raise ValueError(
                    f"Problem class '{cls_name}' not found in known registries."
                )
            items.append(
                ScheduledProblem(
                    problem=prob_cls, waypoint_index=wp_idx, resolved=is_res
                )
            )

        return SelectedProblems(items=items)

    @staticmethod
    def post_expedition_report(
        problems: SelectedProblems,
        report_fpath: str | Path,
        waypoints: list | None = None,
    ) -> None:
        """Append human-readable report summary of all occurring problems."""
        with open(report_fpath, "a", encoding="utf-8") as f:
            for item in problems:
                if waypoints is not None:
                    public_wp = _get_public_wp(item.waypoint_index, waypoints)
                    affected = "in-port" if public_wp is None else f"{public_wp}"
                else:
                    affected = (
                        "in-port"
                        if item.waypoint_index == 0
                        else f"{item.waypoint_index + 1}"
                    )
                delay_hrs = item.problem.delay_duration.total_seconds() / 3600.0
                f.write(
                    f"---\nWaypoint: {affected}\n"
                    f"Problem: {item.problem.message}\n"
                    f"Delay caused: {delay_hrs} hours\n\n"
                )

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
        """
        Display the problem, impact, and result in a live-updating table.

        Sleep times are included to increase readability and engagement for user.
        """
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
