from __future__ import annotations

from collections import defaultdict
from decimal import Decimal
from time import perf_counter

from app.models.enums import (
    AssignmentSource,
    DependencyType,
    TimetableRunStatus,
)
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
from app.scheduling.room_heuristics import ordered_rooms
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

    difficulty: dict[int, tuple[int, int, int]] = {}
    for session_id in session_ids:
        occurrences = [
            occurrence for occurrence in data.occurrences if occurrence.session_id == session_id
        ]
        first = occurrences[0]
        difficulty[session_id] = (
            len(first.allowed_start_room_pairs),
            -first.demand,
            session_id,
        )
    ready = sorted(
        (session_id for session_id, degree in indegree.items() if degree == 0),
        key=difficulty.__getitem__,
    )
    result: list[int] = []
    while ready:
        session_id = ready.pop(0)
        result.append(session_id)
        for successor in sorted(graph[session_id], key=difficulty.__getitem__):
            indegree[successor] -= 1
            if indegree[successor] == 0:
                ready.append(successor)
                ready.sort(key=difficulty.__getitem__)
    return tuple(result)


def _dependency_ok(
    dependency: SessionDependency,
    *,
    candidate_session_id: int,
    candidate_start: StartCandidate,
    placed: dict[tuple[int, int], tuple[SolverAssignment, StartCandidate]],
) -> bool:
    predecessors = tuple(
        value for key, value in placed.items() if key[0] == dependency.predecessor_session_id
    )
    successors = tuple(
        value for key, value in placed.items() if key[0] == dependency.successor_session_id
    )
    if candidate_session_id == dependency.successor_session_id:
        if dependency.dependency_type == DependencyType.DIFFERENT_DAY:
            return all(
                start.day_of_week != candidate_start.day_of_week for _, start in predecessors
            )
        if not predecessors:
            return False
        if dependency.dependency_type == DependencyType.SAME_DAY:
            return any(
                start.day_of_week == candidate_start.day_of_week for _, start in predecessors
            )
        for _, start in predecessors:
            predecessor_end = start.week_index + len(start.occupied_slot_ids)
            if dependency.dependency_type == DependencyType.CONSECUTIVE:
                if (
                    start.day_of_week == candidate_start.day_of_week
                    and predecessor_end == candidate_start.week_index
                ):
                    return True
                continue
            gap = candidate_start.week_index - predecessor_end
            if gap < 0:
                continue
            if dependency.min_gap_slots is not None and gap < dependency.min_gap_slots:
                continue
            if dependency.max_gap_slots is not None and gap > dependency.max_gap_slots:
                continue
            return True
        return False

    if candidate_session_id != dependency.predecessor_session_id or not successors:
        return True
    if dependency.dependency_type == DependencyType.DIFFERENT_DAY:
        return all(start.day_of_week != candidate_start.day_of_week for _, start in successors)
    # Locked successors can be present before a predecessor is greedily placed.
    if dependency.dependency_type == DependencyType.SAME_DAY:
        return any(start.day_of_week == candidate_start.day_of_week for _, start in successors)
    candidate_end = candidate_start.week_index + len(candidate_start.occupied_slot_ids)
    for _, successor_start in successors:
        if dependency.dependency_type == DependencyType.CONSECUTIVE:
            if (
                candidate_start.day_of_week == successor_start.day_of_week
                and candidate_end == successor_start.week_index
            ):
                return True
            continue
        gap = successor_start.week_index - candidate_end
        if gap < 0:
            continue
        if dependency.min_gap_slots is not None and gap < dependency.min_gap_slots:
            continue
        if dependency.max_gap_slots is not None and gap > dependency.max_gap_slots:
            continue
        return True
    return False


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
                    placed=placed,
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
            for occurrence in sorted(
                by_session[session_id],
                key=lambda item: item.occurrence_number,
            ):
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
                        status=TimetableRunStatus.INFEASIBLE,
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

    def __call__(self, db: Session, run: object) -> SolverOutcome:
        data = load_scheduling_input(db, run)  # type: ignore[arg-type]
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
