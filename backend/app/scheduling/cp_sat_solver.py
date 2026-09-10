from __future__ import annotations

from collections import defaultdict
from dataclasses import dataclass
from decimal import Decimal
from time import perf_counter
from typing import Any

from app.models.enums import (
    AssignmentSource,
    DependencyType,
    TimeConstraintType,
    TimetableRunStatus,
)
from app.models.timetable_run import TimetableRun
from app.scheduling.domain import (
    CandidateRoom,
    RoomStrategy,
    SchedulingInput,
    SessionOccurrence,
    SolverAssignment,
    SolverResult,
    StartCandidate,
)
from app.scheduling.greedy_solver import GreedyTimetableSolver
from app.scheduling.input_loader import load_scheduling_input
from app.scheduling.input_validator import require_valid_scheduling_input
from app.scheduling.metrics import calculate_metrics, placement_penalty
from app.scheduling.result_validator import require_valid_solver_result
from app.services.timetable.types import SolverOutcome, TimetableAssignment
from ortools.sat.python import cp_model
from sqlalchemy.orm import Session

MAX_SOLVER_TIME_SECONDS = 60.0
MAX_SEARCH_WORKERS = 8
HYBRID_GREEDY_FAST_PATH_OCCURRENCES = 80

# `solver.parameters.max_time_in_seconds` only bounds the CP-SAT search
# itself. Building the model - in particular the per-occurrence
# AddAllowedAssignments table over every valid (start slot, room) pair - is
# plain Python work that runs *before* that timer starts, and its cost
# scales with the total number of candidate pairs across all occurrences.
# On a full-faculty dataset that table can reach millions of rows, which
# turns "generation" into a many-minutes-long, un-cancellable Python loop
# regardless of the solver time limit. If the input is that large, skip
# building the CP-SAT model altogether and fall back to the much cheaper
# greedy solver so a single result is still produced quickly.
MAX_ALLOWED_PAIRS_FOR_CP_SAT = 20_000


@dataclass(slots=True)
class _OccurrenceVariables:
    occurrence: SessionOccurrence
    starts: tuple[StartCandidate, ...]
    rooms: tuple[CandidateRoom, ...]
    start_option: Any
    room_option: Any
    week_start: Any
    day: Any
    absolute_minute_start: Any
    interval: Any
    start_literals: tuple[Any, ...]
    room_literals: tuple[Any, ...]


def _safe_name(occurrence: SessionOccurrence) -> str:
    return f"s{occurrence.session_id}_o{occurrence.occurrence_number}"


def _filtered_options(
        data: SchedulingInput,
        occurrence: SessionOccurrence,
) -> tuple[tuple[StartCandidate, ...], tuple[CandidateRoom, ...]]:
    allowed_starts = {start_id for start_id, _ in occurrence.allowed_start_room_pairs}
    allowed_rooms = {room_id for _, room_id in occurrence.allowed_start_room_pairs}
    starts = tuple(
        candidate
        for candidate in occurrence.start_candidates
        if candidate.start_slot_id in allowed_starts
    )
    rooms = tuple(room for room in data.rooms if room.id in allowed_rooms)
    return starts, rooms


class CpSatTimetableSolver:
    def __init__(self, *, use_greedy_hints: bool = False) -> None:
        self.use_greedy_hints = use_greedy_hints

    def _greedy_hints(
            self,
            data: SchedulingInput,
    ) -> dict[tuple[int, int], tuple[int, int]]:
        if not self.use_greedy_hints:
            return {}
        baseline = GreedyTimetableSolver(RoomStrategy.BFD).solve(data)
        if baseline.status != TimetableRunStatus.SUCCEEDED:
            return {}
        return {
            assignment.key: (assignment.start_slot_id, assignment.room_id)
            for assignment in baseline.assignments
        }

    @staticmethod
    def _greedy_fallback(
            data: SchedulingInput,
            started: float,
            reason: str,
            **diagnostics: Any,
    ) -> SolverResult | None:
        """Return a fast greedy result instead of building the CP-SAT model.

        Returns None if the greedy solver itself could not find a feasible
        placement, so the caller can proceed to the full CP-SAT attempt (or
        report the failure) instead of silently losing the run.
        """
        baseline = GreedyTimetableSolver(RoomStrategy.BFD).solve(data)
        if baseline.status != TimetableRunStatus.SUCCEEDED:
            baseline = GreedyTimetableSolver(RoomStrategy.FFD).solve(data)
        if baseline.status != TimetableRunStatus.SUCCEEDED:
            return None
        elapsed = int((perf_counter() - started) * 1000)
        return SolverResult(
            status=baseline.status,
            assignments=baseline.assignments,
            objective_score=baseline.objective_score,
            soft_penalty=baseline.soft_penalty,
            execution_time_ms=elapsed,
            diagnostics={
                **baseline.diagnostics,
                "fast_path": reason,
                **diagnostics,
            },
        )

    def solve(self, data: SchedulingInput) -> SolverResult:
        require_valid_scheduling_input(data)
        started = perf_counter()
        occurrence_count = len(data.occurrences)
        total_allowed_pairs = sum(
            len(occurrence.allowed_start_room_pairs) for occurrence in data.occurrences
        )

        # A large Hybrid run does not need a second global CP-SAT search for
        # the demo workflow. The BFD placement is already independently
        # validated and is dramatically faster on a full faculty dataset.
        # Smaller inputs still receive the normal CP-SAT refinement.
        if self.use_greedy_hints and occurrence_count >= HYBRID_GREEDY_FAST_PATH_OCCURRENCES:
            fallback = self._greedy_fallback(
                data,
                started,
                "BFD baseline for large Hybrid input",
                occurrence_count=occurrence_count,
            )
            if fallback is not None:
                return fallback

        # This applies to every algorithm that goes through this solver
        # (plain CP_SAT included), because it is the size of the candidate
        # table - not which algorithm was requested - that drives the
        # Python-side model-building cost described above.
        if total_allowed_pairs >= MAX_ALLOWED_PAIRS_FOR_CP_SAT:
            fallback = self._greedy_fallback(
                data,
                started,
                "BFD baseline: candidate (slot, room) table too large for CP-SAT",
                occurrence_count=occurrence_count,
                total_allowed_pairs=total_allowed_pairs,
                threshold=MAX_ALLOWED_PAIRS_FOR_CP_SAT,
            )
            if fallback is not None:
                return fallback

        model = cp_model.CpModel()
        occurrence_vars: dict[tuple[int, int], _OccurrenceVariables] = {}
        room_intervals: dict[int, list[Any]] = defaultdict(list)
        staff_intervals: dict[int, list[Any]] = defaultdict(list)
        student_intervals: dict[int, list[Any]] = defaultdict(list)
        staff_occupancy_terms: dict[tuple[int, int], list[Any]] = defaultdict(list)
        student_occupancy_terms: dict[tuple[int, int], list[Any]] = defaultdict(list)
        objective_terms: list[Any] = []

        for occurrence in data.occurrences:
            name = _safe_name(occurrence)
            starts, rooms = _filtered_options(data, occurrence)
            start_index = {candidate.start_slot_id: index for index, candidate in enumerate(starts)}
            room_index = {room.id: index for index, room in enumerate(rooms)}
            start_option = model.new_int_var(0, len(starts) - 1, f"start_opt_{name}")
            room_option = model.new_int_var(0, len(rooms) - 1, f"room_opt_{name}")
            week_values = [candidate.week_index for candidate in starts]
            day_values = [candidate.day_of_week for candidate in starts]
            minute_values = [
                candidate.day_of_week * 1440 + candidate.start_minute for candidate in starts
            ]
            week_start = model.new_int_var(
                min(week_values),
                max(week_values),
                f"week_start_{name}",
            )
            day = model.new_int_var(min(day_values), max(day_values), f"day_{name}")
            absolute_minute_start = model.new_int_var(
                min(minute_values),
                max(minute_values),
                f"minute_start_{name}",
            )
            absolute_minute_end = model.new_int_var(
                min(minute_values) + occurrence.duration_minutes,
                max(minute_values) + occurrence.duration_minutes,
                f"minute_end_{name}",
            )
            model.add_element(start_option, week_values, week_start)
            model.add_element(start_option, day_values, day)
            model.add_element(start_option, minute_values, absolute_minute_start)
            model.add(absolute_minute_end == absolute_minute_start + occurrence.duration_minutes)
            interval = model.new_interval_var(
                absolute_minute_start,
                occurrence.duration_minutes,
                absolute_minute_end,
                f"interval_{name}",
            )

            start_literals: list[Any] = []
            for index, candidate in enumerate(starts):
                literal = model.new_bool_var(f"start_{name}_{index}")
                model.add(start_option == index).only_enforce_if(literal)
                model.add(start_option != index).only_enforce_if(literal.negated())
                start_literals.append(literal)
                for slot_id in candidate.occupied_slot_ids:
                    for staff_id in occurrence.staff_ids:
                        staff_occupancy_terms[(staff_id, slot_id)].append(literal)
                    for resource_id in occurrence.student_resource_ids:
                        student_occupancy_terms[(resource_id, slot_id)].append(literal)

            room_literals: list[Any] = []
            for index, room in enumerate(rooms):
                literal = model.new_bool_var(f"room_{name}_{index}")
                model.add(room_option == index).only_enforce_if(literal)
                model.add(room_option != index).only_enforce_if(literal.negated())
                room_literals.append(literal)
                room_interval = model.new_optional_interval_var(
                    absolute_minute_start,
                    occurrence.duration_minutes,
                    absolute_minute_end,
                    literal,
                    f"room_interval_{name}_{room.id}",
                )
                room_intervals[room.id].append(room_interval)

            # Computed once per occurrence rather than once per (start, room)
            # row: it does not depend on either, and this loop can run for
            # tens of thousands of rows on a single occurrence.
            preferred_constraints = tuple(
                constraint
                for constraint in occurrence.time_constraints
                if constraint.constraint_type == TimeConstraintType.PREFERRED_WINDOW
            )
            allowed_cost_rows: list[tuple[int, int, int]] = []
            for start_slot_id, room_id in occurrence.allowed_start_room_pairs:
                if start_slot_id not in start_index or room_id not in room_index:
                    continue
                candidate = starts[start_index[start_slot_id]]
                room = rooms[room_index[room_id]]
                allowed_cost_rows.append(
                    (
                        start_index[start_slot_id],
                        room_index[room_id],
                        placement_penalty(
                            data,
                            occurrence,
                            candidate,
                            room,
                            preferred_constraints=preferred_constraints,
                        ),
                    )
                )
            maximum_cost = max(row[2] for row in allowed_cost_rows)
            placement_cost = model.new_int_var(
                0,
                maximum_cost,
                f"placement_cost_{name}",
            )
            model.add_allowed_assignments(
                [start_option, room_option, placement_cost],
                allowed_cost_rows,
            )
            objective_terms.append(placement_cost)

            for staff_id in occurrence.staff_ids:
                staff_intervals[staff_id].append(interval)
            for resource_id in occurrence.student_resource_ids:
                student_intervals[resource_id].append(interval)

            occurrence_vars[occurrence.key] = _OccurrenceVariables(
                occurrence=occurrence,
                starts=starts,
                rooms=rooms,
                start_option=start_option,
                room_option=room_option,
                week_start=week_start,
                day=day,
                absolute_minute_start=absolute_minute_start,
                interval=interval,
                start_literals=tuple(start_literals),
                room_literals=tuple(room_literals),
            )

        for intervals in room_intervals.values():
            model.add_no_overlap(intervals)
        for intervals in staff_intervals.values():
            model.add_no_overlap(intervals)
        for intervals in student_intervals.values():
            model.add_no_overlap(intervals)

        if data.spread_repeated_occurrences:
            by_session: dict[int, list[_OccurrenceVariables]] = defaultdict(list)
            for variables in occurrence_vars.values():
                by_session[variables.occurrence.session_id].append(variables)
            for session_variables in by_session.values():
                for index, first in enumerate(session_variables):
                    for second in session_variables[index + 1:]:
                        model.add(first.day != second.day)

        by_session_vars: dict[int, list[_OccurrenceVariables]] = defaultdict(list)
        for variables in occurrence_vars.values():
            by_session_vars[variables.occurrence.session_id].append(variables)
        for dependency in data.dependencies:
            predecessors = by_session_vars.get(dependency.predecessor_session_id, [])
            successors = by_session_vars.get(dependency.successor_session_id, [])
            for successor in successors:
                if dependency.dependency_type == DependencyType.DIFFERENT_DAY:
                    for predecessor in predecessors:
                        model.add(predecessor.day != successor.day)
                    continue
                relation_literals: list[Any] = []
                for index, predecessor in enumerate(predecessors):
                    relation = model.new_bool_var(
                        f"dep_{dependency.id}_{successor.occurrence.occurrence_number}_{index}"
                    )
                    relation_literals.append(relation)
                    if dependency.dependency_type == DependencyType.SAME_DAY:
                        model.add(predecessor.day == successor.day).only_enforce_if(relation)
                        continue
                    predecessor_end = predecessor.week_start + predecessor.occurrence.duration_slots
                    if dependency.dependency_type == DependencyType.CONSECUTIVE:
                        model.add(predecessor.day == successor.day).only_enforce_if(relation)
                        model.add(predecessor_end == successor.week_start).only_enforce_if(relation)
                        continue
                    minimum_gap = dependency.min_gap_slots or 0
                    model.add(
                        successor.week_start >= predecessor_end + minimum_gap
                    ).only_enforce_if(relation)
                    if dependency.max_gap_slots is not None:
                        model.add(
                            successor.week_start <= predecessor_end + dependency.max_gap_slots
                        ).only_enforce_if(relation)
                model.add_bool_or(relation_literals)

        for locked in data.locked_assignments:
            variables = occurrence_vars[locked.key]
            locked_start_index = next(
                index
                for index, candidate in enumerate(variables.starts)
                if candidate.start_slot_id == locked.start_slot_id
            )
            locked_room_index = next(
                index for index, room in enumerate(variables.rooms) if room.id == locked.room_id
            )
            model.add(variables.start_option == locked_start_index)
            model.add(variables.room_option == locked_room_index)

        self._add_gap_penalties(
            model,
            data,
            staff_occupancy_terms,
            data.weights.staff_gap,
            objective_terms,
            "staff",
        )
        self._add_gap_penalties(
            model,
            data,
            student_occupancy_terms,
            data.weights.student_gap,
            objective_terms,
            "student",
        )

        hints = self._greedy_hints(data)
        for key, (start_slot_id, room_id) in hints.items():
            variables = occurrence_vars[key]
            hint_start_index = next(
                index
                for index, candidate in enumerate(variables.starts)
                if candidate.start_slot_id == start_slot_id
            )
            hint_room_index = next(
                index for index, room in enumerate(variables.rooms) if room.id == room_id
            )
            model.add_hint(variables.start_option, hint_start_index)
            model.add_hint(variables.room_option, hint_room_index)

        model.minimize(sum(objective_terms))
        solver = cp_model.CpSolver()
        requested_time_limit = float(data.parameters.get("time_limit_seconds", 30.0))
        effective_time_limit = min(MAX_SOLVER_TIME_SECONDS, max(1.0, requested_time_limit))
        requested_workers = int(data.parameters.get("num_search_workers", 8))
        effective_workers = min(MAX_SEARCH_WORKERS, max(1, requested_workers))
        solver.parameters.max_time_in_seconds = effective_time_limit
        solver.parameters.num_search_workers = effective_workers
        solver.parameters.random_seed = int(data.parameters.get("random_seed", 0))
        solver.parameters.log_search_progress = bool(
            data.parameters.get("log_search_progress", False)
        )
        status = solver.solve(model)
        elapsed = int((perf_counter() - started) * 1000)
        if status == cp_model.INFEASIBLE:
            return SolverResult(
                status=TimetableRunStatus.INFEASIBLE,
                execution_time_ms=elapsed,
                diagnostics={
                    "cp_sat_status": solver.status_name(status),
                    "greedy_hint_count": len(hints),
                },
            )
        if status not in {cp_model.OPTIMAL, cp_model.FEASIBLE}:
            # A time-limited CP-SAT search can return UNKNOWN even though the
            # constructive baseline already found a valid placement. Keep the
            # request useful by returning that validated baseline instead of
            # converting a timeout into a failed generation run.
            if status == cp_model.UNKNOWN:
                fallback = self._greedy_fallback(
                    data,
                    started,
                    "BFD baseline after CP-SAT search timeout",
                    cp_sat_status=solver.status_name(status),
                    requested_time_limit_seconds=requested_time_limit,
                    effective_time_limit_seconds=effective_time_limit,
                )
                if fallback is not None:
                    return fallback
            return SolverResult(
                status=TimetableRunStatus.FAILED,
                execution_time_ms=elapsed,
                diagnostics={
                    "cp_sat_status": solver.status_name(status),
                    "message": "No feasible solution was found before the search stopped.",
                },
            )

        locked_keys = {locked.key for locked in data.locked_assignments}
        assignments: list[SolverAssignment] = []
        for key, variables in sorted(occurrence_vars.items()):
            start = variables.starts[solver.value(variables.start_option)]
            room = variables.rooms[solver.value(variables.room_option)]
            is_locked = key in locked_keys
            assignments.append(
                SolverAssignment(
                    course_session_id=key[0],
                    occurrence_number=key[1],
                    room_id=room.id,
                    start_slot_id=start.start_slot_id,
                    is_locked=is_locked,
                    assignment_source=(
                        AssignmentSource.PRESERVED if is_locked else AssignmentSource.SOLVER
                    ),
                )
            )
        assignment_tuple = tuple(assignments)
        require_valid_solver_result(data, assignment_tuple)
        metrics = calculate_metrics(data, assignment_tuple)
        return SolverResult(
            status=TimetableRunStatus.SUCCEEDED,
            assignments=assignment_tuple,
            objective_score=Decimal(str(solver.objective_value)),
            soft_penalty=Decimal(metrics.soft_penalty),
            execution_time_ms=elapsed,
            diagnostics={
                **metrics.as_dict(),
                "cp_sat_status": solver.status_name(status),
                "best_objective_bound": solver.best_objective_bound,
                "branches": solver.num_branches,
                "conflicts": solver.num_conflicts,
                "greedy_hint_count": len(hints),
                "requested_time_limit_seconds": requested_time_limit,
                "effective_time_limit_seconds": effective_time_limit,
                "effective_search_workers": effective_workers,
            },
        )

    @staticmethod
    def _add_gap_penalties(
            model: cp_model.CpModel,
            data: SchedulingInput,
            occupancy_terms: dict[tuple[int, int], list[Any]],
            weight: int,
            objective_terms: list[Any],
            label: str,
    ) -> None:
        if weight == 0:
            return
        resource_term_counts: dict[int, int] = defaultdict(int)
        for (resource_id, _), terms in occupancy_terms.items():
            resource_term_counts[resource_id] += len(terms)
        resource_ids = sorted(
            resource_id
            for resource_id, term_count in resource_term_counts.items()
            if term_count > 1
        )
        slots_by_day: dict[int, list[int]] = defaultdict(list)
        for slot in data.slots:
            slots_by_day[slot.day_of_week].append(slot.id)
        slot_by_id = data.slot_by_id
        for slot_ids in slots_by_day.values():
            slot_ids.sort(key=lambda slot_id: slot_by_id[slot_id].slot_index)
        zero = model.new_constant(0)
        for resource_id in resource_ids:
            for day, slot_ids in slots_by_day.items():
                occupied: list[Any] = []
                for slot_id in slot_ids:
                    terms = occupancy_terms.get((resource_id, slot_id), [])
                    if not terms:
                        occupied.append(zero)
                        continue
                    cell = model.new_bool_var(f"{label}_{resource_id}_d{day}_slot{slot_id}")
                    model.add(sum(terms) == cell)
                    occupied.append(cell)
                for index in range(1, len(occupied) - 1):
                    before = model.new_bool_var(f"{label}_{resource_id}_d{day}_before{index}")
                    after = model.new_bool_var(f"{label}_{resource_id}_d{day}_after{index}")
                    model.add_max_equality(before, occupied[:index])
                    model.add_max_equality(after, occupied[index + 1:])
                    gap = model.new_bool_var(f"{label}_{resource_id}_d{day}_gap{index}")
                    model.add(gap <= before)
                    model.add(gap <= after)
                    model.add(gap + occupied[index] <= 1)
                    model.add(gap >= before + after - occupied[index] - 1)
                    objective_terms.append(gap * weight)

    def __call__(self, db: Session, run: TimetableRun) -> SolverOutcome:
        data = load_scheduling_input(db, run)
        result = self.solve(data)
        persisted = tuple(
            TimetableAssignment(
                course_session_id=assignment.course_session_id,
                occurrence_number=assignment.occurrence_number,
                room_id=assignment.room_id,
                start_slot_id=assignment.start_slot_id,
            )
            for assignment in result.assignments
            if not assignment.is_locked
        )
        return SolverOutcome(
            status=result.status,
            assignments=persisted,
            objective_score=result.objective_score,
            soft_penalty=result.soft_penalty,
            execution_time_ms=result.execution_time_ms,
            diagnostics=result.diagnostics,
        )


class HybridTimetableSolver(CpSatTimetableSolver):
    def __init__(self) -> None:
        super().__init__(use_greedy_hints=True)


__all__ = ["CpSatTimetableSolver", "HybridTimetableSolver"]