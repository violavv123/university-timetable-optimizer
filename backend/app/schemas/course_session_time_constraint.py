from datetime import time
from typing import Self

from pydantic import BaseModel, ConfigDict, Field, model_validator

from app.models.enums import DayOfWeek, TimeConstraintType


PREFERRED_TIME_CONSTRAINT_TYPES = {TimeConstraintType.PREFERRED_WINDOW}
HARD_TIME_CONSTRAINT_TYPES = {
    TimeConstraintType.ALLOWED_WINDOW,
    TimeConstraintType.FORBIDDEN_WINDOW,
    TimeConstraintType.FIXED_WINDOW,
}


class CourseSessionTimeConstraintBase(BaseModel):
    model_config = ConfigDict(extra="forbid")

    course_session_id: int = Field(..., gt=0)
    day_of_week: DayOfWeek | None = None
    start_time: time
    end_time: time
    constraint_type: TimeConstraintType
    preference_weight: int | None = Field(default=None, ge=0, le=32767)

    @model_validator(mode="after")
    def validate_time_constraint(self) -> Self:
        if self.end_time <= self.start_time:
            raise ValueError("end_time must be after start_time")

        if (
            self.constraint_type in PREFERRED_TIME_CONSTRAINT_TYPES
            and self.preference_weight is None
        ):
            raise ValueError("preferred windows require preference_weight")

        if (
            self.constraint_type in HARD_TIME_CONSTRAINT_TYPES
            and self.preference_weight is not None
        ):
            raise ValueError("hard time constraints cannot have preference_weight")

        return self


class CourseSessionTimeConstraintCreate(CourseSessionTimeConstraintBase):
    pass


class CourseSessionTimeConstraintUpdate(BaseModel):
    model_config = ConfigDict(extra="forbid")

    course_session_id: int | None = Field(default=None, gt=0)
    day_of_week: DayOfWeek | None = None
    start_time: time | None = None
    end_time: time | None = None
    constraint_type: TimeConstraintType | None = None
    preference_weight: int | None = Field(default=None, ge=0, le=32767)

    @model_validator(mode="after")
    def reject_locally_inconsistent_patch(self) -> Self:
        if (
            self.start_time is not None
            and self.end_time is not None
            and self.end_time <= self.start_time
        ):
            raise ValueError("end_time must be after start_time")

        if (
            self.constraint_type in HARD_TIME_CONSTRAINT_TYPES
            and self.preference_weight is not None
        ):
            raise ValueError("hard time constraints cannot have preference_weight")

        if (
            self.constraint_type in PREFERRED_TIME_CONSTRAINT_TYPES
            and "preference_weight" in self.model_fields_set
            and self.preference_weight is None
        ):
            raise ValueError("preferred windows require preference_weight")

        return self


class CourseSessionTimeConstraintRead(CourseSessionTimeConstraintBase):
    model_config = ConfigDict(from_attributes=True, extra="forbid")

    id: int = Field(..., gt=0)
