from dataclasses import dataclass, field
from decimal import Decimal
from typing import Any

from app.models.enums import AssignmentSource, TimetableRunStatus


@dataclass(frozen=True, slots=True)
class TimetableAssignment:
    course_session_id: int
    occurrence_number: int
    room_id: int
    start_slot_id: int
    is_locked: bool = False
    assignment_source: AssignmentSource = AssignmentSource.SOLVER


@dataclass(frozen=True, slots=True)
class SolverOutcome:
    status: TimetableRunStatus
    assignments: tuple[TimetableAssignment, ...] = ()
    objective_score: Decimal | None = None
    soft_penalty: Decimal | None = None
    execution_time_ms: int | None = None
    diagnostics: dict[str, Any] = field(default_factory=dict)


@dataclass(frozen=True, slots=True)
class TimetableConflict:
    code: str
    message: str
    details: dict[str, Any] = field(default_factory=dict)


@dataclass(frozen=True, slots=True)
class TimetableValidationResult:
    timetable_run_id: int
    hard_conflicts: tuple[TimetableConflict, ...]
    expected_occurrences: int
    actual_entries: int

    @property
    def is_valid(self) -> bool:
        return not self.hard_conflicts

    @property
    def hard_conflict_count(self) -> int:
        return len(self.hard_conflicts)
