from datetime import time
from typing import Self

from app.models.enums import DayOfWeek
from pydantic import BaseModel, ConfigDict, Field, model_validator


class TimeSlotBase(BaseModel):
    model_config = ConfigDict(extra="forbid")

    scheduling_profile_id: int = Field(..., gt=0)
    day_of_week: DayOfWeek
    slot_index: int = Field(..., ge=0, le=32767)
    start_time: time
    end_time: time

    @model_validator(mode="after")
    def validate_time_range(self) -> Self:
        if self.end_time <= self.start_time:
            raise ValueError("end_time must be after start_time")
        return self


class TimeSlotCreate(TimeSlotBase):
    is_active: bool = True


class TimeSlotUpdate(BaseModel):
    model_config = ConfigDict(extra="forbid")

    scheduling_profile_id: int | None = Field(default=None, gt=0)
    day_of_week: DayOfWeek | None = None
    slot_index: int | None = Field(default=None, ge=0, le=32767)
    start_time: time | None = None
    end_time: time | None = None
    is_active: bool | None = None

    @model_validator(mode="after")
    def validate_supplied_time_range(self) -> Self:
        if (
            self.start_time is not None
            and self.end_time is not None
            and self.end_time <= self.start_time
        ):
            raise ValueError("end_time must be after start_time")
        return self


class TimeSlotRead(TimeSlotBase):
    model_config = ConfigDict(from_attributes=True, extra="forbid")

    id: int = Field(..., gt=0)
    is_active: bool
