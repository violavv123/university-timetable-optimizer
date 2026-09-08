from __future__ import annotations

from dataclasses import dataclass, field
from decimal import Decimal
from enum import StrEnum
from typing import Any, Protocol

from app.models.enums import (
    AssignmentSource,
    AvailabilityType,
    ComponentType,
    DependencyType,
    RoomType,
    StudentGroupType,
    TeachingRole,
    TimeConstraintType,
    TimetableRunStatus,
)


class RoomStrategy(StrEnum):
    FFD = "FFD"
    BFD = "BFD"


@dataclass(frozen=True, slots=True)
class SchedulingSlot:
    id: int
    day_of_week: int
    slot_index: int
    start_minute: int
    end_minute: int
    week_index: int


@dataclass(frozen=True, slots=True)
class StartCandidate:
    start_slot_id: int
    day_of_week: int
    start_minute: int
    end_minute: int
    week_index: int
    occupied_slot_ids: tuple[int, ...]


@dataclass(frozen=True, slots=True)
class CandidateRoom:
    id: int
    code: str
    capacity: int
    room_type: RoomType


@dataclass(frozen=True, slots=True)
class AvailabilityWindow:
    owner_id: int
    day_of_week: int
    start_minute: int
    end_minute: int
    availability_type: AvailabilityType
    preference_weight: int = 0


@dataclass(frozen=True, slots=True)
class SessionTimeConstraint:
    day_of_week: int | None
    start_minute: int
    end_minute: int
    constraint_type: TimeConstraintType
    preference_weight: int = 0


@dataclass(frozen=True, slots=True)
class StaffAssignment:
    staff_member_id: int
    teaching_role: TeachingRole
    is_primary: bool
    is_active: bool
    is_qualified: bool


@dataclass(frozen=True, slots=True)
class StudentGroupData:
    id: int
    program_semester_id: int
    academic_term_id: int
    parent_group_id: int | None
    group_type: StudentGroupType
    student_count: int
    is_active: bool


@dataclass(frozen=True, slots=True)
class SessionOccurrence:
    session_id: int
    occurrence_number: int
    weekly_frequency: int
    duration_slots: int
    duration_minutes: int
    component_type: ComponentType
    curriculum_periods: int
    demand: int
    calculated_attendance: int
    offering_expected_students: int | None
    declared_max_students: int | None
    required_room_type: RoomType | None
    required_room_id: int | None
    program_id: int
    program_semester_id: int
    academic_term_id: int
    level_code: str
    direct_group_ids: frozenset[int]
    student_resource_ids: frozenset[int]
    staff_ids: frozenset[int]
    staff_assignments: tuple[StaffAssignment, ...]
    time_constraints: tuple[SessionTimeConstraint, ...]
    start_candidates: tuple[StartCandidate, ...]
    compatible_room_ids: frozenset[int]
    allowed_start_room_pairs: frozenset[tuple[int, int]]

    @property
    def key(self) -> tuple[int, int]:
        return (self.session_id, self.occurrence_number)


@dataclass(frozen=True, slots=True)
class SessionDependency:
    id: int
    predecessor_session_id: int
    successor_session_id: int
    dependency_type: DependencyType
    min_gap_slots: int | None = None
    max_gap_slots: int | None = None


@dataclass(frozen=True, slots=True)
class LockedAssignment:
    course_session_id: int
    occurrence_number: int
    room_id: int
    start_slot_id: int

    @property
    def key(self) -> tuple[int, int]:
        return (self.course_session_id, self.occurrence_number)


@dataclass(frozen=True, slots=True)
class SchedulingWeights:
    preferred_room: int
    historical_room: int
    student_gap: int
    staff_gap: int
    late_hour: int
    unused_seat: int = 1


@dataclass(frozen=True, slots=True)
class SchedulingInput:
    timetable_run_id: int
    academic_term_id: int
    scheduling_profile_id: int
    faculty_id: int
    slot_minutes: int
    max_lecture_students: int
    max_numerical_students: int
    max_lab_students: int
    slots: tuple[SchedulingSlot, ...]
    rooms: tuple[CandidateRoom, ...]
    groups: tuple[StudentGroupData, ...]
    occurrences: tuple[SessionOccurrence, ...]
    dependencies: tuple[SessionDependency, ...]
    locked_assignments: tuple[LockedAssignment, ...]
    staff_availability: dict[int, tuple[AvailabilityWindow, ...]]
    room_availability: dict[int, tuple[AvailabilityWindow, ...]]
    program_room_preferences: dict[int, dict[int, int]]
    historical_rooms: dict[int, frozenset[int]]
    weights: SchedulingWeights
    parameters: dict[str, Any] = field(default_factory=dict)

    @property
    def spread_repeated_occurrences(self) -> bool:
        value = self.parameters.get("spread_repeated_occurrences", True)
        return value if isinstance(value, bool) else True

    @property
    def room_by_id(self) -> dict[int, CandidateRoom]:
        return {room.id: room for room in self.rooms}

    @property
    def slot_by_id(self) -> dict[int, SchedulingSlot]:
        return {slot.id: slot for slot in self.slots}

    @property
    def occurrence_by_key(self) -> dict[tuple[int, int], SessionOccurrence]:
        return {occurrence.key: occurrence for occurrence in self.occurrences}


@dataclass(frozen=True, slots=True)
class SolverAssignment:
    course_session_id: int
    occurrence_number: int
    room_id: int
    start_slot_id: int
    is_locked: bool = False
    assignment_source: AssignmentSource = AssignmentSource.SOLVER

    @property
    def key(self) -> tuple[int, int]:
        return (self.course_session_id, self.occurrence_number)


@dataclass(frozen=True, slots=True)
class SolverResult:
    status: TimetableRunStatus
    assignments: tuple[SolverAssignment, ...] = ()
    objective_score: Decimal | None = None
    soft_penalty: Decimal | None = None
    execution_time_ms: int | None = None
    diagnostics: dict[str, Any] = field(default_factory=dict)


@dataclass(frozen=True, slots=True)
class ValidationIssue:
    code: str
    message: str
    details: dict[str, Any] = field(default_factory=dict)


@dataclass(frozen=True, slots=True)
class SchedulingValidationResult:
    issues: tuple[ValidationIssue, ...] = ()

    @property
    def is_valid(self) -> bool:
        return not self.issues


class TimetableSolver(Protocol):
    def solve(self, data: SchedulingInput) -> SolverResult: ...

    def __call__(self, db: Any, run: Any) -> Any: ...


__all__ = [
    "AvailabilityWindow",
    "CandidateRoom",
    "LockedAssignment",
    "RoomStrategy",
    "SchedulingInput",
    "SchedulingSlot",
    "SchedulingValidationResult",
    "SchedulingWeights",
    "SessionDependency",
    "SessionOccurrence",
    "SessionTimeConstraint",
    "SolverAssignment",
    "SolverResult",
    "StaffAssignment",
    "StartCandidate",
    "StudentGroupData",
    "TimetableSolver",
    "ValidationIssue",
]
