from __future__ import annotations

from collections import defaultdict

from app.core.exceptions import BusinessRuleError
from app.scheduling.dependency_rules import dependency_satisfied
from app.scheduling.domain import (
    SchedulingInput,
    SchedulingValidationResult,
    SessionOccurrence,
    SolverAssignment,
    StartCandidate,
    ValidationIssue,
)


def _issue(
    issues: list[ValidationIssue],
    code: str,
    message: str,
    **details: object,
) -> None:
    issue = ValidationIssue(code=code, message=message, details=dict(details))
    fingerprint = (issue.code, repr(sorted(issue.details.items())))
    if fingerprint not in {
        (existing.code, repr(sorted(existing.details.items()))) for existing in issues
    }:
        issues.append(issue)


def _candidate(
    occurrence: SessionOccurrence,
    start_slot_id: int,
) -> StartCandidate | None:
    return next(
        (
            candidate
            for candidate in occurrence.start_candidates
            if candidate.start_slot_id == start_slot_id
        ),
        None,
    )


def validate_solver_result(
    data: SchedulingInput,
    assignments: tuple[SolverAssignment, ...],
) -> SchedulingValidationResult:
    issues: list[ValidationIssue] = []
    occurrence_by_key = data.occurrence_by_key
    assignment_by_key: dict[tuple[int, int], SolverAssignment] = {}
    resolved: dict[
        tuple[int, int],
        tuple[SolverAssignment, SessionOccurrence, StartCandidate],
    ] = {}
    for assignment in assignments:
        if assignment.key in assignment_by_key:
            _issue(
                issues,
                "DUPLICATE_OCCURRENCE_ASSIGNMENT",
                "Every occurrence must receive exactly one assignment.",
                course_session_id=assignment.course_session_id,
                occurrence_number=assignment.occurrence_number,
            )
            continue
        assignment_by_key[assignment.key] = assignment
        occurrence = occurrence_by_key.get(assignment.key)
        if occurrence is None:
            _issue(
                issues,
                "UNKNOWN_OCCURRENCE_ASSIGNMENT",
                "The result contains an occurrence outside the scheduling input.",
                course_session_id=assignment.course_session_id,
                occurrence_number=assignment.occurrence_number,
            )
            continue
        start = _candidate(occurrence, assignment.start_slot_id)
        if start is None:
            _issue(
                issues,
                "INVALID_START_ASSIGNMENT",
                "The result uses a start slot that violates duration or time constraints.",
                course_session_id=assignment.course_session_id,
                occurrence_number=assignment.occurrence_number,
                start_slot_id=assignment.start_slot_id,
            )
            continue
        if (
            assignment.start_slot_id,
            assignment.room_id,
        ) not in occurrence.allowed_start_room_pairs:
            _issue(
                issues,
                "INVALID_START_ROOM_ASSIGNMENT",
                "The selected room/start pair violates a hard room constraint.",
                course_session_id=assignment.course_session_id,
                occurrence_number=assignment.occurrence_number,
                start_slot_id=assignment.start_slot_id,
                room_id=assignment.room_id,
            )
            continue
        resolved[assignment.key] = (assignment, occurrence, start)

    missing = set(occurrence_by_key).difference(assignment_by_key)
    for session_id, occurrence_number in sorted(missing):
        _issue(
            issues,
            "MISSING_OCCURRENCE_ASSIGNMENT",
            "Every occurrence must receive exactly one room and start slot.",
            course_session_id=session_id,
            occurrence_number=occurrence_number,
        )

    locked_by_key = {locked.key: locked for locked in data.locked_assignments}
    for key, locked in locked_by_key.items():
        locked_result = assignment_by_key.get(key)
        if locked_result is None:
            continue
        if (
            locked_result.room_id != locked.room_id
            or locked_result.start_slot_id != locked.start_slot_id
        ):
            _issue(
                issues,
                "LOCKED_ENTRY_CHANGED",
                "Locked entries must preserve their room and start slot.",
                course_session_id=key[0],
                occurrence_number=key[1],
            )

    if data.spread_repeated_occurrences:
        days_by_session: dict[int, list[int]] = defaultdict(list)
        for _, occurrence, start in resolved.values():
            days_by_session[occurrence.session_id].append(start.day_of_week)
        for session_id, days in days_by_session.items():
            if len(days) != len(set(days)):
                _issue(
                    issues,
                    "REPEATED_OCCURRENCES_SAME_DAY",
                    "Repeated occurrences must use different days.",
                    course_session_id=session_id,
                    days=days,
                )

    room_usage: dict[tuple[int, int], list[tuple[int, int]]] = defaultdict(list)
    staff_usage: dict[tuple[int, int], list[tuple[int, int]]] = defaultdict(list)
    student_usage: dict[tuple[int, int], list[tuple[int, int]]] = defaultdict(list)
    for assignment, occurrence, start in resolved.values():
        for slot_id in start.occupied_slot_ids:
            room_usage[(assignment.room_id, slot_id)].append(assignment.key)
            for staff_id in occurrence.staff_ids:
                staff_usage[(staff_id, slot_id)].append(assignment.key)
            for student_resource_id in occurrence.student_resource_ids:
                student_usage[(student_resource_id, slot_id)].append(assignment.key)

    for (room_id, slot_id), keys in room_usage.items():
        if len(keys) > 1:
            _issue(
                issues,
                "ROOM_OVERLAP",
                "A room cannot host overlapping occurrences.",
                room_id=room_id,
                time_slot_id=slot_id,
                occurrences=sorted(keys),
            )
    for (staff_id, slot_id), keys in staff_usage.items():
        if len(keys) > 1:
            _issue(
                issues,
                "STAFF_OVERLAP",
                "A staff member cannot teach overlapping occurrences.",
                staff_member_id=staff_id,
                time_slot_id=slot_id,
                occurrences=sorted(keys),
            )
    for (student_resource_id, slot_id), keys in student_usage.items():
        if len(keys) > 1:
            _issue(
                issues,
                "STUDENT_GROUP_OVERLAP",
                "Identical or hierarchy-related student groups cannot overlap.",
                student_resource_id=student_resource_id,
                time_slot_id=slot_id,
                occurrences=sorted(keys),
            )

    by_session: dict[
        int,
        list[tuple[SolverAssignment, StartCandidate]],
    ] = defaultdict(list)
    for assignment, occurrence, start in resolved.values():
        by_session[occurrence.session_id].append((assignment, start))
    for dependency in data.dependencies:
        predecessors = tuple(by_session.get(dependency.predecessor_session_id, ()))
        successors = tuple(by_session.get(dependency.successor_session_id, ()))
        if not predecessors or not successors:
            continue
        for successor in successors:
            predecessor_starts = (start for _, start in predecessors)
            if not dependency_satisfied(dependency, predecessor_starts, successor[1]):
                _issue(
                    issues,
                    "DEPENDENCY_VIOLATION",
                    "A session dependency is not satisfied.",
                    dependency_id=dependency.id,
                    dependency_type=dependency.dependency_type.value,
                    successor_occurrence=successor[0].key,
                )
    return SchedulingValidationResult(issues=tuple(issues))


def require_valid_solver_result(
    data: SchedulingInput,
    assignments: tuple[SolverAssignment, ...],
) -> None:
    result = validate_solver_result(data, assignments)
    if result.is_valid:
        return
    raise BusinessRuleError(
        "The solver produced an invalid timetable.",
        details={
            "issue_count": len(result.issues),
            "issues": [
                {
                    "code": issue.code,
                    "message": issue.message,
                    "details": issue.details,
                }
                for issue in result.issues
            ],
        },
    )


__all__ = ["require_valid_solver_result", "validate_solver_result"]
