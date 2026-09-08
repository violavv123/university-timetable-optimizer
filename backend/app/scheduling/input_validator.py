from __future__ import annotations

from collections import defaultdict
from collections.abc import Mapping

from app.core.exceptions import BusinessRuleError
from app.models.enums import (
    AvailabilityType,
    ComponentType,
    DependencyType,
    StudentGroupType,
    TeachingRole,
    TimeConstraintType,
)
from app.scheduling.dependency_rules import dependency_satisfied
from app.scheduling.domain import (
    AvailabilityWindow,
    SchedulingInput,
    SchedulingValidationResult,
    SessionOccurrence,
    StartCandidate,
    StudentGroupData,
    ValidationIssue,
)


def _issue(
    issues: list[ValidationIssue],
    code: str,
    message: str,
    **details: object,
) -> None:
    candidate = ValidationIssue(code=code, message=message, details=dict(details))
    fingerprint = (candidate.code, repr(sorted(candidate.details.items())))
    if fingerprint not in {(issue.code, repr(sorted(issue.details.items()))) for issue in issues}:
        issues.append(candidate)


def _overlaps(first: AvailabilityWindow, second: AvailabilityWindow) -> bool:
    return (
        first.day_of_week == second.day_of_week
        and first.start_minute < second.end_minute
        and first.end_minute > second.start_minute
    )


def _validate_parameters(data: SchedulingInput, issues: list[ValidationIssue]) -> None:
    numeric_positive = ("time_limit_seconds",)
    integer_positive = ("num_search_workers",)
    integer_nonnegative = (
        "random_seed",
        "unused_seat_weight",
        "master_evening_weight",
    )
    for key in numeric_positive:
        value = data.parameters.get(key)
        if value is not None and (
            isinstance(value, bool) or not isinstance(value, (int, float)) or value <= 0
        ):
            _issue(
                issues,
                "INVALID_SOLVER_PARAMETER",
                f"{key} must be a positive number.",
                parameter=key,
            )
    for key in integer_positive:
        value = data.parameters.get(key)
        if value is not None and (
            isinstance(value, bool) or not isinstance(value, int) or value <= 0
        ):
            _issue(
                issues,
                "INVALID_SOLVER_PARAMETER",
                f"{key} must be a positive integer.",
                parameter=key,
            )
    for key in integer_nonnegative:
        value = data.parameters.get(key)
        if value is not None and (
            isinstance(value, bool) or not isinstance(value, int) or value < 0
        ):
            _issue(
                issues,
                "INVALID_SOLVER_PARAMETER",
                f"{key} must be a nonnegative integer.",
                parameter=key,
            )
    spread = data.parameters.get("spread_repeated_occurrences")
    if spread is not None and not isinstance(spread, bool):
        _issue(
            issues,
            "INVALID_SOLVER_PARAMETER",
            "spread_repeated_occurrences must be a boolean.",
            parameter="spread_repeated_occurrences",
        )
    log_progress = data.parameters.get("log_search_progress")
    if log_progress is not None and not isinstance(log_progress, bool):
        _issue(
            issues,
            "INVALID_SOLVER_PARAMETER",
            "log_search_progress must be a boolean.",
            parameter="log_search_progress",
        )
    master_start = data.parameters.get("master_evening_start_minute", 17 * 60)
    master_end = data.parameters.get("master_evening_end_minute", 20 * 60)
    if (
        isinstance(master_start, bool)
        or not isinstance(master_start, int)
        or not 0 <= master_start < 24 * 60
    ):
        _issue(
            issues,
            "INVALID_SOLVER_PARAMETER",
            "master_evening_start_minute must be an integer from 0 through 1439.",
            parameter="master_evening_start_minute",
        )
    if (
        isinstance(master_end, bool)
        or not isinstance(master_end, int)
        or not 0 < master_end <= 24 * 60
    ):
        _issue(
            issues,
            "INVALID_SOLVER_PARAMETER",
            "master_evening_end_minute must be an integer from 1 through 1440.",
            parameter="master_evening_end_minute",
        )
    if (
        isinstance(master_start, int)
        and not isinstance(master_start, bool)
        and isinstance(master_end, int)
        and not isinstance(master_end, bool)
        and master_start >= master_end
    ):
        _issue(
            issues,
            "INVALID_SOLVER_PARAMETER",
            "The master evening start must be earlier than its end.",
            parameter="master_evening_window",
        )


def _validate_availability(
    rows_by_owner: dict[int, tuple[AvailabilityWindow, ...]],
    resource_name: str,
    issues: list[ValidationIssue],
) -> None:
    contradictory = {
        frozenset({AvailabilityType.AVAILABLE, AvailabilityType.UNAVAILABLE}),
        frozenset({AvailabilityType.PREFERRED, AvailabilityType.AVOID}),
    }
    for owner_id, rows in rows_by_owner.items():
        for row in rows:
            if row.start_minute >= row.end_minute:
                _issue(
                    issues,
                    "INVALID_AVAILABILITY_WINDOW",
                    f"{resource_name} availability must have a positive duration.",
                    owner_id=owner_id,
                )
            weighted = row.availability_type in {
                AvailabilityType.PREFERRED,
                AvailabilityType.AVOID,
            }
            if weighted and row.preference_weight <= 0:
                _issue(
                    issues,
                    "INVALID_AVAILABILITY_WEIGHT",
                    f"{resource_name} preference windows require a positive weight.",
                    owner_id=owner_id,
                )
        for index, first in enumerate(rows):
            for second in rows[index + 1 :]:
                pair = frozenset({first.availability_type, second.availability_type})
                if pair in contradictory and _overlaps(first, second):
                    _issue(
                        issues,
                        "CONTRADICTORY_AVAILABILITY",
                        f"{resource_name} has contradictory overlapping windows.",
                        owner_id=owner_id,
                        day_of_week=first.day_of_week,
                    )


def _validate_slots(data: SchedulingInput, issues: list[ValidationIssue]) -> None:
    if not data.slots:
        _issue(
            issues,
            "NO_ACTIVE_TIME_SLOTS",
            "The scheduling profile has no active time slots.",
        )
        return
    seen_positions: set[tuple[int, int]] = set()
    seen_starts: set[tuple[int, int]] = set()
    for slot in data.slots:
        position = (slot.day_of_week, slot.slot_index)
        start = (slot.day_of_week, slot.start_minute)
        if position in seen_positions or start in seen_starts:
            _issue(
                issues,
                "DUPLICATE_TIME_SLOT",
                "Active profile slots must have unique day/index and day/start pairs.",
                day_of_week=slot.day_of_week,
                slot_index=slot.slot_index,
            )
        seen_positions.add(position)
        seen_starts.add(start)
        if slot.end_minute - slot.start_minute != data.slot_minutes:
            _issue(
                issues,
                "SLOT_DURATION_MISMATCH",
                "Each active time slot must match the profile's slot_minutes.",
                time_slot_id=slot.id,
                expected_minutes=data.slot_minutes,
                actual_minutes=slot.end_minute - slot.start_minute,
            )


def _group_ancestors(
    group_id: int,
    groups: Mapping[int, StudentGroupData],
) -> tuple[int, ...]:
    ancestors: list[int] = []
    seen = {group_id}
    current = groups.get(group_id)
    parent_id = current.parent_group_id if current is not None else None
    while parent_id is not None and parent_id in groups and parent_id not in seen:
        ancestors.append(parent_id)
        seen.add(parent_id)
        parent_id = groups[parent_id].parent_group_id
    return tuple(ancestors)


def _validate_groups(data: SchedulingInput, issues: list[ValidationIssue]) -> None:
    groups = {group.id: group for group in data.groups}
    current_groups = {
        group.id: group
        for group in data.groups
        if group.academic_term_id == data.academic_term_id and group.is_active
    }
    children: dict[int, list[StudentGroupData]] = defaultdict(list)
    limits = {
        StudentGroupType.LECTURE_GROUP: data.max_lecture_students,
        StudentGroupType.NUMERICAL_GROUP: data.max_numerical_students,
        StudentGroupType.LAB_GROUP: data.max_lab_students,
    }
    expected_parent_type = {
        StudentGroupType.LECTURE_GROUP: StudentGroupType.COHORT,
        StudentGroupType.NUMERICAL_GROUP: StudentGroupType.LECTURE_GROUP,
        StudentGroupType.LAB_GROUP: StudentGroupType.NUMERICAL_GROUP,
    }
    for group in current_groups.values():
        limit = limits.get(group.group_type)
        if limit is not None and group.student_count > limit:
            _issue(
                issues,
                "GROUP_SIZE_LIMIT_EXCEEDED",
                "Student group size exceeds its scheduling-profile limit.",
                student_group_id=group.id,
                student_count=group.student_count,
                maximum=limit,
            )
        if group.parent_group_id is None:
            if group.group_type != StudentGroupType.COHORT:
                _issue(
                    issues,
                    "INVALID_GROUP_HIERARCHY",
                    "Only a cohort may be a hierarchy root.",
                    student_group_id=group.id,
                )
            continue
        parent = groups.get(group.parent_group_id)
        if parent is None:
            _issue(
                issues,
                "MISSING_GROUP_PARENT",
                "A student group's parent does not exist.",
                student_group_id=group.id,
                parent_group_id=group.parent_group_id,
            )
            continue
        children[group.parent_group_id].append(group)
        if (
            not parent.is_active
            or parent.academic_term_id != group.academic_term_id
            or parent.program_semester_id != group.program_semester_id
            or expected_parent_type.get(group.group_type) != parent.group_type
        ):
            _issue(
                issues,
                "INVALID_GROUP_HIERARCHY",
                "Parent and child groups must be active, term/semester "
                "compatible, and adjacent hierarchy types.",
                student_group_id=group.id,
                parent_group_id=parent.id,
            )
        ancestors = _group_ancestors(group.id, groups)
        if group.id in ancestors or (
            ancestors and groups[ancestors[-1]].parent_group_id is not None
        ):
            _issue(
                issues,
                "GROUP_HIERARCHY_CYCLE",
                "Student-group hierarchy contains a cycle or broken ancestor chain.",
                student_group_id=group.id,
            )
    for parent_id, child_rows in children.items():
        parent = groups[parent_id]
        total = sum(child.student_count for child in child_rows if child.is_active)
        if parent.is_active and total != parent.student_count:
            _issue(
                issues,
                "GROUP_CHILD_TOTAL_MISMATCH",
                "Active child-group totals must equal their active parent's student count.",
                parent_group_id=parent_id,
                parent_student_count=parent.student_count,
                child_student_count=total,
            )


def _component_limit(data: SchedulingInput, occurrence: SessionOccurrence) -> int:
    if occurrence.component_type == ComponentType.LECTURE:
        return data.max_lecture_students
    if occurrence.component_type == ComponentType.NUMERICAL:
        return data.max_numerical_students
    return data.max_lab_students


def _validate_occurrences(data: SchedulingInput, issues: list[ValidationIssue]) -> None:
    groups = {group.id: group for group in data.groups}
    by_session: dict[int, list[SessionOccurrence]] = defaultdict(list)
    for occurrence in data.occurrences:
        by_session[occurrence.session_id].append(occurrence)

    for session_id, occurrences in by_session.items():
        first = occurrences[0]
        actual_numbers = {occurrence.occurrence_number for occurrence in occurrences}
        expected_numbers = set(range(1, first.weekly_frequency + 1))
        if len(actual_numbers) != len(occurrences):
            _issue(
                issues,
                "DUPLICATE_OCCURRENCE_NUMBER",
                "An occurrence number may appear only once within a session.",
                course_session_id=session_id,
            )
        if actual_numbers != expected_numbers:
            _issue(
                issues,
                "INVALID_OCCURRENCE_SET",
                "Occurrences must be numbered from 1 through weekly_frequency.",
                course_session_id=session_id,
                expected=sorted(expected_numbers),
                actual=sorted(actual_numbers),
            )
        invariant_fields = (
            "weekly_frequency",
            "duration_slots",
            "duration_minutes",
            "component_type",
            "curriculum_periods",
            "demand",
            "program_semester_id",
            "academic_term_id",
            "direct_group_ids",
            "student_resource_ids",
            "staff_ids",
            "staff_assignments",
            "time_constraints",
            "start_candidates",
            "compatible_room_ids",
            "allowed_start_room_pairs",
        )
        if any(
            any(getattr(occurrence, field) != getattr(first, field) for field in invariant_fields)
            for occurrence in occurrences[1:]
        ):
            _issue(
                issues,
                "INCONSISTENT_OCCURRENCE_DATA",
                "Occurrences of one session must share the same scheduling data.",
                course_session_id=session_id,
            )
        if first.weekly_frequency * first.duration_slots != first.curriculum_periods:
            _issue(
                issues,
                "COURSE_WORKLOAD_MISMATCH",
                "Session frequency multiplied by duration must match curriculum periods.",
                course_session_id=session_id,
                scheduled_periods=first.weekly_frequency * first.duration_slots,
                curriculum_periods=first.curriculum_periods,
            )
        selected = first.direct_group_ids
        for group_id in selected:
            group = groups.get(group_id)
            if group is None:
                _issue(
                    issues,
                    "MISSING_SESSION_GROUP",
                    "A session references a missing student group.",
                    course_session_id=session_id,
                    student_group_id=group_id,
                )
                continue
            if (
                not group.is_active
                or group.academic_term_id != data.academic_term_id
                or group.program_semester_id != first.program_semester_id
            ):
                _issue(
                    issues,
                    "INCOMPATIBLE_SESSION_GROUP",
                    "Session groups must be active and match the selected term "
                    "and program semester.",
                    course_session_id=session_id,
                    student_group_id=group_id,
                )
            ancestor_ids = set(_group_ancestors(group_id, groups))
            conflicting = selected.intersection(ancestor_ids)
            if conflicting:
                _issue(
                    issues,
                    "AMBIGUOUS_SESSION_GROUP_HIERARCHY",
                    "A session cannot include both a student group and one of its ancestors.",
                    course_session_id=session_id,
                    student_group_ids=sorted({group_id, *conflicting}),
                )
        if not selected and first.offering_expected_students is None:
            _issue(
                issues,
                "MISSING_SESSION_ATTENDANCE",
                "A session requires groups or an offering-level expected student fallback.",
                course_session_id=session_id,
            )
        if (
            first.declared_max_students is not None
            and first.declared_max_students < first.calculated_attendance
        ):
            _issue(
                issues,
                "SESSION_MAX_STUDENTS_TOO_SMALL",
                "max_students cannot be below calculated group attendance.",
                course_session_id=session_id,
                max_students=first.declared_max_students,
                calculated_attendance=first.calculated_attendance,
            )
        if first.demand > _component_limit(data, first):
            _issue(
                issues,
                "SESSION_GROUP_LIMIT_EXCEEDED",
                "Session demand exceeds the component limit in the scheduling profile.",
                course_session_id=session_id,
                demand=first.demand,
                maximum=_component_limit(data, first),
            )
        expected_role = {
            ComponentType.LECTURE: TeachingRole.LECTURER,
            ComponentType.NUMERICAL: TeachingRole.NUMERICAL_INSTRUCTOR,
            ComponentType.LABORATORY: TeachingRole.LAB_INSTRUCTOR,
        }[first.component_type]
        if len(first.staff_assignments) == 0:
            _issue(
                issues,
                "MISSING_SESSION_STAFF",
                "Every scheduled session requires assigned staff.",
                course_session_id=session_id,
            )
        if sum(assignment.is_primary for assignment in first.staff_assignments) != 1:
            _issue(
                issues,
                "INVALID_PRIMARY_STAFF_COUNT",
                "Every scheduled session requires exactly one primary staff member.",
                course_session_id=session_id,
            )
        for assignment in first.staff_assignments:
            if (
                not assignment.is_active
                or not assignment.is_qualified
                or assignment.teaching_role != expected_role
            ):
                _issue(
                    issues,
                    "INVALID_STAFF_QUALIFICATION",
                    "Assigned staff must be active, qualified, and use the "
                    "component's teaching role.",
                    course_session_id=session_id,
                    staff_member_id=assignment.staff_member_id,
                )
        for constraint in first.time_constraints:
            if constraint.start_minute >= constraint.end_minute:
                _issue(
                    issues,
                    "INVALID_SESSION_TIME_WINDOW",
                    "Session time constraints must have a positive duration.",
                    course_session_id=session_id,
                )
            if (
                constraint.constraint_type == TimeConstraintType.PREFERRED_WINDOW
                and constraint.preference_weight <= 0
            ):
                _issue(
                    issues,
                    "INVALID_SESSION_PREFERENCE_WEIGHT",
                    "Preferred session windows require a positive weight.",
                    course_session_id=session_id,
                )
        if not first.start_candidates:
            _issue(
                issues,
                "NO_FEASIBLE_START",
                "No complete active-slot interval satisfies session and staff constraints.",
                course_session_id=session_id,
            )
        if not first.compatible_room_ids:
            _issue(
                issues,
                "NO_COMPATIBLE_ROOM",
                "No active room satisfies required room, type, and capacity constraints.",
                course_session_id=session_id,
                demand=first.demand,
            )
        if not first.allowed_start_room_pairs:
            _issue(
                issues,
                "NO_FEASIBLE_START_ROOM_PAIR",
                "Room availability removes every otherwise compatible placement.",
                course_session_id=session_id,
            )
        if data.spread_repeated_occurrences and first.weekly_frequency > 1:
            feasible_days = {candidate.day_of_week for candidate in first.start_candidates}
            if len(feasible_days) < first.weekly_frequency:
                _issue(
                    issues,
                    "INSUFFICIENT_DAYS_FOR_REPEATED_SESSION",
                    "Repeated weekly occurrences require distinct feasible days.",
                    course_session_id=session_id,
                    weekly_frequency=first.weekly_frequency,
                    feasible_days=sorted(feasible_days),
                )


def _validate_dependencies(data: SchedulingInput, issues: list[ValidationIssue]) -> None:
    session_ids = {occurrence.session_id for occurrence in data.occurrences}
    pair_types: dict[tuple[int, int], set[DependencyType]] = defaultdict(set)
    graph: dict[int, set[int]] = {session_id: set() for session_id in session_ids}
    for dependency in data.dependencies:
        if (
            dependency.predecessor_session_id not in session_ids
            or dependency.successor_session_id not in session_ids
        ):
            _issue(
                issues,
                "DEPENDENCY_INPUT_MISMATCH",
                "Dependency endpoints must both belong to the active selected-term input.",
                dependency_id=dependency.id,
            )
            continue
        pair = (
            dependency.predecessor_session_id,
            dependency.successor_session_id,
        )
        pair_types[pair].add(dependency.dependency_type)
        if dependency.dependency_type in {
            DependencyType.PRECEDES,
            DependencyType.CONSECUTIVE,
        }:
            graph[pair[0]].add(pair[1])
    for pair, types in pair_types.items():
        if DependencyType.SAME_DAY in types and DependencyType.DIFFERENT_DAY in types:
            _issue(
                issues,
                "CONTRADICTORY_DEPENDENCY",
                "The same dependency pair cannot require both same and different days.",
                predecessor_session_id=pair[0],
                successor_session_id=pair[1],
            )

    visiting: set[int] = set()
    visited: set[int] = set()

    def visit(session_id: int) -> None:
        if session_id in visiting:
            _issue(
                issues,
                "DEPENDENCY_CYCLE",
                "Ordering dependencies contain an indirect cycle.",
                course_session_id=session_id,
            )
            return
        if session_id in visited:
            return
        visiting.add(session_id)
        for successor_id in graph[session_id]:
            visit(successor_id)
        visiting.remove(session_id)
        visited.add(session_id)

    for session_id in graph:
        visit(session_id)


def _validate_locked_assignments(
    data: SchedulingInput,
    issues: list[ValidationIssue],
) -> None:
    occurrences = data.occurrence_by_key
    seen: set[tuple[int, int]] = set()
    resolved: dict[tuple[int, int], tuple[SessionOccurrence, StartCandidate, int]] = {}
    for locked in data.locked_assignments:
        if locked.key in seen:
            _issue(
                issues,
                "DUPLICATE_LOCKED_OCCURRENCE",
                "At most one locked entry may exist for an occurrence.",
                course_session_id=locked.course_session_id,
                occurrence_number=locked.occurrence_number,
            )
            continue
        seen.add(locked.key)
        occurrence = occurrences.get(locked.key)
        if occurrence is None:
            _issue(
                issues,
                "LOCKED_ENTRY_INPUT_MISMATCH",
                "A locked entry must refer to an active occurrence in the run's term.",
                course_session_id=locked.course_session_id,
                occurrence_number=locked.occurrence_number,
            )
            continue
        if (locked.start_slot_id, locked.room_id) not in occurrence.allowed_start_room_pairs:
            _issue(
                issues,
                "INVALID_LOCKED_PLACEMENT",
                "A locked entry no longer satisfies current hard constraints.",
                course_session_id=locked.course_session_id,
                occurrence_number=locked.occurrence_number,
                room_id=locked.room_id,
                start_slot_id=locked.start_slot_id,
            )
            continue
        start = next(
            (
                candidate
                for candidate in occurrence.start_candidates
                if candidate.start_slot_id == locked.start_slot_id
            ),
            None,
        )
        if start is None:
            _issue(
                issues,
                "INVALID_LOCKED_PLACEMENT",
                "A locked entry must use one of the occurrence's feasible starts.",
                course_session_id=locked.course_session_id,
                occurrence_number=locked.occurrence_number,
                start_slot_id=locked.start_slot_id,
            )
            continue
        resolved[locked.key] = (occurrence, start, locked.room_id)

    if data.spread_repeated_occurrences:
        days_by_session: dict[int, list[int]] = defaultdict(list)
        for occurrence, start, _ in resolved.values():
            days_by_session[occurrence.session_id].append(start.day_of_week)
        for session_id, days in days_by_session.items():
            if len(days) != len(set(days)):
                _issue(
                    issues,
                    "LOCKED_REPEATED_OCCURRENCES_SAME_DAY",
                    "Locked repeated occurrences must use different days.",
                    course_session_id=session_id,
                    days=days,
                )

    room_usage: dict[tuple[int, int], list[tuple[int, int]]] = defaultdict(list)
    staff_usage: dict[tuple[int, int], list[tuple[int, int]]] = defaultdict(list)
    student_usage: dict[tuple[int, int], list[tuple[int, int]]] = defaultdict(list)
    for key, (occurrence, start, room_id) in resolved.items():
        for slot_id in start.occupied_slot_ids:
            room_usage[(room_id, slot_id)].append(key)
            for staff_id in occurrence.staff_ids:
                staff_usage[(staff_id, slot_id)].append(key)
            for resource_id in occurrence.student_resource_ids:
                student_usage[(resource_id, slot_id)].append(key)

    usage_kinds = (
        ("ROOM", room_usage),
        ("STAFF", staff_usage),
        ("STUDENT_GROUP", student_usage),
    )
    for resource_kind, usage in usage_kinds:
        for (resource_id, slot_id), keys in usage.items():
            if len(keys) > 1:
                _issue(
                    issues,
                    f"LOCKED_{resource_kind}_OVERLAP",
                    "Locked entries contain an unavoidable resource overlap.",
                    resource_id=resource_id,
                    time_slot_id=slot_id,
                    occurrences=sorted(keys),
                )

    occurrence_keys_by_session: dict[int, set[tuple[int, int]]] = defaultdict(set)
    locked_keys_by_session: dict[int, set[tuple[int, int]]] = defaultdict(set)
    for occurrence in data.occurrences:
        occurrence_keys_by_session[occurrence.session_id].add(occurrence.key)
    for key in resolved:
        locked_keys_by_session[key[0]].add(key)
    fully_locked_sessions = {
        session_id
        for session_id, keys in occurrence_keys_by_session.items()
        if keys and keys == locked_keys_by_session.get(session_id, set())
    }
    for dependency in data.dependencies:
        if not {
            dependency.predecessor_session_id,
            dependency.successor_session_id,
        }.issubset(fully_locked_sessions):
            continue
        predecessor_starts = tuple(
            start
            for key, (_, start, _) in resolved.items()
            if key[0] == dependency.predecessor_session_id
        )
        successor_starts = tuple(
            start
            for key, (_, start, _) in resolved.items()
            if key[0] == dependency.successor_session_id
        )
        for successor_start in successor_starts:
            if not dependency_satisfied(dependency, predecessor_starts, successor_start):
                _issue(
                    issues,
                    "LOCKED_DEPENDENCY_VIOLATION",
                    "Fully locked sessions violate a dependency and cannot be repaired.",
                    dependency_id=dependency.id,
                    dependency_type=dependency.dependency_type.value,
                )


def validate_scheduling_input(data: SchedulingInput) -> SchedulingValidationResult:
    issues: list[ValidationIssue] = []
    _validate_parameters(data, issues)
    _validate_slots(data, issues)
    if not data.rooms:
        _issue(
            issues,
            "NO_ACTIVE_ROOMS",
            "The scheduling profile's faculty has no active rooms.",
        )
    if not data.occurrences:
        _issue(
            issues,
            "NO_SCHEDULABLE_SESSIONS",
            "The selected term has no active READY sessions requiring a timetable.",
        )
    _validate_availability(data.staff_availability, "Staff", issues)
    _validate_availability(data.room_availability, "Room", issues)
    _validate_groups(data, issues)
    _validate_occurrences(data, issues)
    _validate_dependencies(data, issues)
    _validate_locked_assignments(data, issues)
    return SchedulingValidationResult(issues=tuple(issues))


def require_valid_scheduling_input(data: SchedulingInput) -> None:
    result = validate_scheduling_input(data)
    if result.is_valid:
        return
    raise BusinessRuleError(
        "Timetable input validation failed.",
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


__all__ = ["require_valid_scheduling_input", "validate_scheduling_input"]
