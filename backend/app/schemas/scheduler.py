from datetime import time
from decimal import Decimal
from typing import Annotated, Self

from app.models.enums import DayOfWeek, SchedulingAlgorithm, TimetableRunStatus
from app.schemas.timetable_run import TimetableRunRead
from pydantic import BaseModel, ConfigDict, Field, JsonValue, model_validator

PositiveId = Annotated[int, Field(gt=0)]


class TimetableGenerationRequest(BaseModel):
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)

    academic_term_id: int = Field(..., gt=0)
    scheduling_profile_id: int = Field(..., gt=0)
    name: str = Field(..., min_length=1, max_length=150)
    algorithm: SchedulingAlgorithm = SchedulingAlgorithm.HYBRID
    parameters: dict[str, JsonValue] = Field(default_factory=dict)


class TimetableReoptimizationRequest(BaseModel):
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)

    source_timetable_run_id: int = Field(..., gt=0)
    name: str = Field(..., min_length=1, max_length=150)
    algorithm: SchedulingAlgorithm = SchedulingAlgorithm.HYBRID
    preserve_locked_entries: bool = True
    parameters: dict[str, JsonValue] = Field(default_factory=dict)


class SchedulingConflictRead(BaseModel):
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)

    conflict_type: str = Field(..., min_length=1, max_length=100)
    message: str = Field(..., min_length=1, max_length=2000)
    course_session_ids: list[PositiveId] = Field(default_factory=list)
    staff_member_ids: list[PositiveId] = Field(default_factory=list)
    student_group_ids: list[PositiveId] = Field(default_factory=list)
    room_ids: list[PositiveId] = Field(default_factory=list)
    day_of_week: DayOfWeek | None = None
    start_time: time | None = None
    end_time: time | None = None

    @model_validator(mode="after")
    def validate_optional_time_range(self) -> Self:
        if (self.start_time is None) != (self.end_time is None):
            raise ValueError("start_time and end_time must be provided together")

        if (
            self.start_time is not None
            and self.end_time is not None
            and self.end_time <= self.start_time
        ):
            raise ValueError("end_time must be after start_time")

        return self


class RoomUtilizationRead(BaseModel):
    """Per-room utilization calculated over active profile slots."""

    model_config = ConfigDict(extra="forbid")

    room_id: int = Field(..., gt=0)
    assigned_slots: int = Field(..., ge=0)
    available_slots: int = Field(..., ge=0)
    utilization_percent: Decimal = Field(
        ...,
        ge=0,
        le=100,
        max_digits=5,
        decimal_places=2,
    )


class SolverStatisticsRead(BaseModel):
    model_config = ConfigDict(extra="forbid")

    status: TimetableRunStatus
    objective_score: Decimal | None = Field(
        default=None,
        max_digits=14,
        decimal_places=4,
    )
    hard_conflicts: int = Field(..., ge=0)
    soft_penalty: Decimal | None = Field(
        default=None,
        ge=0,
        max_digits=14,
        decimal_places=4,
    )
    execution_time_ms: int | None = Field(default=None, ge=0)
    assigned_occurrences: int = Field(..., ge=0)
    unassigned_occurrences: int = Field(..., ge=0)
    room_utilization: list[RoomUtilizationRead] = Field(default_factory=list)


class TimetableValidationResult(BaseModel):
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)

    is_valid: bool
    hard_conflicts: int = Field(..., ge=0)
    warnings: list[str] = Field(default_factory=list)
    conflicts: list[SchedulingConflictRead] = Field(default_factory=list)

    @model_validator(mode="after")
    def validate_consistency(self) -> Self:
        if self.is_valid != (self.hard_conflicts == 0):
            raise ValueError("is_valid must be true exactly when hard_conflicts is zero")
        return self


class TimetableGenerationResponse(BaseModel):
    """Works for synchronous results and asynchronously started runs."""

    model_config = ConfigDict(extra="forbid")

    timetable_run: TimetableRunRead
    statistics: SolverStatisticsRead | None = None
    validation: TimetableValidationResult | None = None
