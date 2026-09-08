from pydantic import BaseModel, ConfigDict, Field


class SchedulingProfileBase(BaseModel):
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)

    faculty_id: int = Field(..., gt=0)
    name: str = Field(..., min_length=1, max_length=150)
    slot_minutes: int = Field(default=45, gt=0, le=1440)
    max_lecture_students: int = Field(default=60, gt=0)
    max_numerical_students: int = Field(default=40, gt=0)
    max_lab_students: int = Field(default=20, gt=0)
    preferred_room_weight: int = Field(default=1, ge=0, le=32767)
    historical_room_weight: int = Field(default=1, ge=0, le=32767)
    student_gap_weight: int = Field(default=1, ge=0, le=32767)
    staff_gap_weight: int = Field(default=1, ge=0, le=32767)
    late_hour_weight: int = Field(default=1, ge=0, le=32767)


class SchedulingProfileCreate(SchedulingProfileBase):
    is_active: bool = True


class SchedulingProfileUpdate(BaseModel):
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)

    faculty_id: int | None = Field(default=None, gt=0)
    name: str | None = Field(default=None, min_length=1, max_length=150)
    slot_minutes: int | None = Field(default=None, gt=0, le=1440)
    max_lecture_students: int | None = Field(default=None, gt=0)
    max_numerical_students: int | None = Field(default=None, gt=0)
    max_lab_students: int | None = Field(default=None, gt=0)
    preferred_room_weight: int | None = Field(default=None, ge=0, le=32767)
    historical_room_weight: int | None = Field(default=None, ge=0, le=32767)
    student_gap_weight: int | None = Field(default=None, ge=0, le=32767)
    staff_gap_weight: int | None = Field(default=None, ge=0, le=32767)
    late_hour_weight: int | None = Field(default=None, ge=0, le=32767)
    is_active: bool | None = None


class SchedulingProfileRead(SchedulingProfileBase):
    model_config = ConfigDict(from_attributes=True, extra="forbid")

    id: int = Field(..., gt=0)
    is_active: bool
