from datetime import time
from typing import Self

from app.models.enums import AvailabilityType, DayOfWeek
from pydantic import BaseModel, ConfigDict, Field, model_validator

PREFERENCE_TYPES = {AvailabilityType.PREFERRED, AvailabilityType.AVOID}
HARD_AVAILABILITY_TYPES = {AvailabilityType.AVAILABLE, AvailabilityType.UNAVAILABLE}


class StaffAvailabilityBase(BaseModel):
    model_config = ConfigDict(extra="forbid")

    staff_member_id: int = Field(..., gt=0)
    academic_term_id: int = Field(..., gt=0)
    day_of_week: DayOfWeek
    start_time: time
    end_time: time
    availability_type: AvailabilityType
    preference_weight: int | None = Field(default=None, ge=0, le=32767)

    @model_validator(mode="after")
    def validate_availability_window(self) -> Self:
        if self.end_time <= self.start_time:
            raise ValueError("end_time must be after start_time")

        if self.availability_type in PREFERENCE_TYPES and self.preference_weight is None:
            raise ValueError("preferred and avoid windows require preference_weight")

        if self.availability_type in HARD_AVAILABILITY_TYPES and self.preference_weight is not None:
            raise ValueError("available and unavailable windows cannot have preference_weight")

        return self


class StaffAvailabilityCreate(StaffAvailabilityBase):
    pass


class StaffAvailabilityUpdate(BaseModel):
    model_config = ConfigDict(extra="forbid")

    staff_member_id: int | None = Field(default=None, gt=0)
    academic_term_id: int | None = Field(default=None, gt=0)
    day_of_week: DayOfWeek | None = None
    start_time: time | None = None
    end_time: time | None = None
    availability_type: AvailabilityType | None = None
    preference_weight: int | None = Field(default=None, ge=0, le=32767)

    @model_validator(mode="after")
    def reject_locally_inconsistent_patch(self) -> Self:
        if (
            self.start_time is not None
            and self.end_time is not None
            and self.end_time <= self.start_time
        ):
            raise ValueError("end_time must be after start_time")

        if self.availability_type in HARD_AVAILABILITY_TYPES and self.preference_weight is not None:
            raise ValueError("available and unavailable windows cannot have preference_weight")

        if (
            self.availability_type in PREFERENCE_TYPES
            and "preference_weight" in self.model_fields_set
            and self.preference_weight is None
        ):
            raise ValueError("preferred and avoid windows require preference_weight")

        return self


class StaffAvailabilityRead(StaffAvailabilityBase):
    model_config = ConfigDict(from_attributes=True, extra="forbid")

    id: int = Field(..., gt=0)
