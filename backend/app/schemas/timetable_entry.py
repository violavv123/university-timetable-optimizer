from typing import Self

from pydantic import AwareDatetime, BaseModel, ConfigDict, Field, model_validator

from app.models.enums import AssignmentSource


class TimetableEntryBase(BaseModel):
    model_config = ConfigDict(extra="forbid")

    timetable_run_id: int = Field(..., gt=0)
    course_session_id: int = Field(..., gt=0)
    occurrence_number: int = Field(..., gt=0, le=32767)
    room_id: int = Field(..., gt=0)
    start_slot_id: int = Field(..., gt=0)


class TimetableEntryCreate(TimetableEntryBase):
    is_locked: bool = False
    assignment_source: AssignmentSource = AssignmentSource.SOLVER


class TimetableEntryUpdate(BaseModel):
    """A manual placement update; identifying occurrence fields are immutable."""

    model_config = ConfigDict(extra="forbid")

    room_id: int | None = Field(default=None, gt=0)
    start_slot_id: int | None = Field(default=None, gt=0)

    @model_validator(mode="after")
    def require_change(self) -> Self:
        if not self.model_fields_set:
            raise ValueError("at least one field must be provided")
        if any(getattr(self, field_name) is None for field_name in self.model_fields_set):
            raise ValueError("room_id and start_slot_id cannot be null")
        return self


class TimetableEntryRead(TimetableEntryCreate):
    model_config = ConfigDict(from_attributes=True, extra="forbid")

    id: int = Field(..., gt=0)
    created_at: AwareDatetime


class TimetableEntryBulkItem(BaseModel):
    """One entry inside a single-run bulk write."""

    model_config = ConfigDict(extra="forbid")

    course_session_id: int = Field(..., gt=0)
    occurrence_number: int = Field(..., gt=0, le=32767)
    room_id: int = Field(..., gt=0)
    start_slot_id: int = Field(..., gt=0)
    is_locked: bool = False
    assignment_source: AssignmentSource = AssignmentSource.SOLVER


class TimetableEntryBulkCreate(BaseModel):
    model_config = ConfigDict(extra="forbid")

    timetable_run_id: int = Field(..., gt=0)
    entries: list[TimetableEntryBulkItem] = Field(
        ...,
        min_length=1,
        max_length=10000,
    )

    @model_validator(mode="after")
    def reject_duplicate_occurrences(self) -> Self:
        keys = [
            (entry.course_session_id, entry.occurrence_number)
            for entry in self.entries
        ]
        if len(keys) != len(set(keys)):
            raise ValueError(
                "entries cannot contain duplicate course-session occurrences"
            )
        return self


class TimetableEntryLockUpdate(BaseModel):
    model_config = ConfigDict(extra="forbid")

    is_locked: bool
