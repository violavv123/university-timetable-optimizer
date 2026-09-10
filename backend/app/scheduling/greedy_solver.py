from __future__ import annotations

from collections import defaultdict
from decimal import Decimal
from time import perf_counter

from app.models.enums import (
    AssignmentSource,
    DependencyType,
    TimetableRunStatus,
)
from app.models.timetable_run import TimetableRun
from app.scheduling.dependency_rules import dependency_satisfied
from app.scheduling.domain import (
    RoomStrategy,
    SchedulingInput,
    SessionDependency,
    SessionOccurrence,
    SolverAssignment,
    SolverResult,
    StartCandidate,
)
from app.scheduling.input_loader import load_scheduling_input
from app.scheduling.input_validator import require_valid_scheduling_input
from app.scheduling.metrics import calculate_metrics
from app.scheduling.result_validator import require_valid_solver_result
from app.scheduling.room_heuristics import (
    decreasing_occurrence_order,
    occurrence_difficulty_key,
    ordered_rooms,
)
from app.services.timetable.types import SolverOutcome, TimetableAssignment
from sqlalchemy.orm import Session


def _candidate_for(
        occurrence: SessionOccurrence,
        start_slot_id: int,
) -> StartCandidate:
    return next(
        candidate
        for candidate in occurrence.start_candidates
        if candidate.start_slot_id == start_slot_id
    )


def _session_order(data: SchedulingInput) -> tuple[int, ...]:
    session_ids = {occurrence.session_id for occurrence in data.occurrences}
    graph: dict[int, set[int]] = {session_id: set() for session_id in session_ids}
    indegree = dict.fromkeys(session_ids, 0)
    for dependency in data.dependencies:
        if dependency.dependency_type not in {
            DependencyType.PRECEDES,
            DependencyType.CONSECUTIVE,
        }:
            continue
        predecessor = dependency.predecessor_session_id
        successor = dependency.successor_session_id
        if predecessor not in session_ids or successor not in session_ids:
            continue
        if successor not in graph[predecessor]:
            graph[predecessor].add(successor)
            indegree[successor] += 1

    first_by_session: dict[int, SessionOccurrence] = {}
    for session_id in session_ids:
        occurrences = [
            occurrence for occurrence in data.occurrences if occurrence.session_id == session_id
        ]
        first_by_session[session_id] = decreasing_occurrence_order(occurrences)[0]

    def difficulty(session_id: int) -> tuple[bool, int, int, int, int, int]:
        return occurrence_difficulty_key(first_by_session[session_id])

    ready = sorted(
        (session_id for session_id, degree in indegree.items() if degree == 0),
        key=difficulty,
    )
    result: list[int] = []
    while ready:
        session_id = ready.pop(0)
        result.append(session_id)
        for successor in sorted(graph[session_id], key=difficulty):
            indegree[successor] -= 1
            if indegree[successor] == 0:
                ready.append(successor)
                ready.sort(key=difficulty)
    return tuple(result)


def _dependency_ok(
        dependency: SessionDependency,
        *,
        candidate_session_id: int,
        candidate_start: StartCandidate,
        placed_starts_by_session: dict[int, list[StartCandidate]],
) -> bool:
    predecessors = tuple(placed_starts_by_session.get(dependency.predecessor_session_id, ()))
    successors = tuple(placed_starts_by_session.get(dependency.successor_session_id, ()))
    if candidate_session_id == dependency.successor_session_id:
        # A symmetric relationship may be encountered before its predecessor.
        # Defer the check; it will be enforced when the predecessor is placed
        # and again by the independent result validator.
        if not predecessors:
            return True
        return dependency_satisfied(dependency, predecessors, candidate_start)

    if candidate_session_id != dependency.predecessor_session_id or not successors:
        return True
    all_predecessors = (*predecessors, candidate_start)
    return all(
        dependency_satisfied(dependency, all_predecessors, successor_start)
        for successor_start in successors
    )


class GreedyTimetableSolver:
    def __init__(self, room_strategy: RoomStrategy) -> None:
        self.room_strategy = room_strategy

    def solve(self, data: SchedulingInput) -> SolverResult:
        require_valid_scheduling_input(data)
        started = perf_counter()
        room_usage: set[tuple[int, int]] = set()
        staff_usage: set[tuple[int, int]] = set()
        student_usage: set[tuple[int, int]] = set()
        used_days: dict[int, set[int]] = defaultdict(set)
        placed: dict[
            tuple[int, int],
            tuple[SolverAssignment, StartCandidate],
        ] = {}
        # `_dependency_ok` used to scan every placed assignment on every call
        # (it needs the already-placed starts for the other side of the
        # dependency). That is O(number of placed occurrences) per check, and
        # it is checked on every room/start candidate attempt for every
        # occurrence involved in a dependency - quadratic in the number of
        # occurrences on datasets with many session dependencies. Keeping a
        # running index by session id makes each lookup O(1) instead.
        placed_starts_by_session: dict[int, list[StartCandidate]] = defaultdict(list)

        def resources_fit(
                occurrence: SessionOccurrence,
                start: StartCandidate,
                room_id: int,
                *,
                check_dependencies: bool = True,
        ) -> bool:
            for slot_id in start.occupied_slot_ids:
                if (room_id, slot_id) in room_usage:
                    return False
                if any((staff_id, slot_id) in staff_usage for staff_id in occurrence.staff_ids):
                    return False
                if any(
                        (resource_id, slot_id) in student_usage
                        for resource_id in occurrence.student_resource_ids
                ):
                    return False
            if (
                    data.spread_repeated_occurrences
                    and start.day_of_week in used_days[occurrence.session_id]
            ):
                return False
            return not check_dependencies or all(
                _dependency_ok(
                    dependency,
                    candidate_session_id=occurrence.session_id,
                    candidate_start=start,
                    placed_starts_by_session=placed_starts_by_session,
                )
                for dependency in data.dependencies
                if occurrence.session_id
                in {
                    dependency.predecessor_session_id,
                    dependency.successor_session_id,
                }
            )

        def add_assignment(
                occurrence: SessionOccurrence,
                start: StartCandidate,
                room_id: int,
                *,
                locked: bool,
        ) -> bool:
            if not resources_fit(
                    occurrence,
                    start,
                    room_id,
                    check_dependencies=not locked,
            ):
                return False
            assignment = SolverAssignment(
                course_session_id=occurrence.session_id,
                occurrence_number=occurrence.occurrence_number,
                room_id=room_id,
                start_slot_id=start.start_slot_id,
                is_locked=locked,
                assignment_source=(
                    AssignmentSource.PRESERVED if locked else AssignmentSource.SOLVER
                ),
            )
            placed[occurrence.key] = (assignment, start)
            placed_starts_by_session[occurrence.session_id].append(start)
            used_days[occurrence.session_id].add(start.day_of_week)
            for slot_id in start.occupied_slot_ids:
                room_usage.add((room_id, slot_id))
                staff_usage.update((staff_id, slot_id) for staff_id in occurrence.staff_ids)
                student_usage.update(
                    (resource_id, slot_id) for resource_id in occurrence.student_resource_ids
                )
            return True

        occurrence_by_key = data.occurrence_by_key
        for locked in data.locked_assignments:
            occurrence = occurrence_by_key[locked.key]
            start = _candidate_for(occurrence, locked.start_slot_id)
            if not add_assignment(occurrence, start, locked.room_id, locked=True):
                elapsed = int((perf_counter() - started) * 1000)
                return SolverResult(
                    status=TimetableRunStatus.INFEASIBLE,
                    execution_time_ms=elapsed,
                    diagnostics={
                        "reason": "locked_entries_conflict",
                        "occurrence": locked.key,
                    },
                )

        by_session: dict[int, list[SessionOccurrence]] = defaultdict(list)
        for occurrence in data.occurrences:
            by_session[occurrence.session_id].append(occurrence)
        for session_id in _session_order(data):
            for occurrence in decreasing_occurrence_order(by_session[session_id]):
                if occurrence.key in placed:
                    continue
                assigned = False
                for start in sorted(
                        occurrence.start_candidates,
                        key=lambda candidate: (
                                candidate.week_index,
                                candidate.start_slot_id,
                        ),
                ):
                    for room in ordered_rooms(
                            occurrence,
                            start,
                            data.rooms,
                            self.room_strategy,
                    ):
                        if add_assignment(
                                occurrence,
                                start,
                                room.id,
                                locked=False,
                        ):
                            assigned = True
                            break
                    if assigned:
                        break
                if not assigned:
                    elapsed = int((perf_counter() - started) * 1000)
                    return SolverResult(
                        # A constructive heuristic cannot prove mathematical
                        # infeasibility because it does not backtrack.
                        status=TimetableRunStatus.FAILED,
                        execution_time_ms=elapsed,
                        diagnostics={
                            "reason": "greedy_search_exhausted",
                            "course_session_id": occurrence.session_id,
                            "occurrence_number": occurrence.occurrence_number,
                            "room_strategy": self.room_strategy.value,
                        },
                    )

        assignments = tuple(value[0] for _, value in sorted(placed.items()))
        require_valid_solver_result(data, assignments)
        metrics = calculate_metrics(data, assignments)
        elapsed = int((perf_counter() - started) * 1000)
        return SolverResult(
            status=TimetableRunStatus.SUCCEEDED,
            assignments=assignments,
            objective_score=Decimal(metrics.soft_penalty),
            soft_penalty=Decimal(metrics.soft_penalty),
            execution_time_ms=elapsed,
            diagnostics={
                **metrics.as_dict(),
                "room_strategy": self.room_strategy.value,
            },
        )

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


__all__ = ["GreedyTimetableSolver"]
