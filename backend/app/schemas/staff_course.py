from typing import Self

from pydantic import BaseModel, ConfigDict, Field, model_validator


class StaffCourseBase(BaseModel):
    model_config = ConfigDict(extra="forbid")

    staff_member_id: int = Field(..., gt=0)
    course_id: int = Field(..., gt=0)
    can_lecture: bool = False
    can_assist: bool = False

    @model_validator(mode="after")
    def validate_qualification(self) -> Self:
        if not self.can_lecture and not self.can_assist:
            raise ValueError("at least one of can_lecture or can_assist must be true")
        return self


class StaffCourseCreate(StaffCourseBase):
    is_active: bool = True


class StaffCourseUpdate(BaseModel):
    model_config = ConfigDict(extra="forbid")

    staff_member_id: int | None = Field(default=None, gt=0)
    course_id: int | None = Field(default=None, gt=0)
    can_lecture: bool | None = None
    can_assist: bool | None = None
    is_active: bool | None = None

    @model_validator(mode="after")
    def reject_invalid_complete_permission_patch(self) -> Self:
        if {"can_lecture", "can_assist"}.issubset(self.model_fields_set):
            if not self.can_lecture and not self.can_assist:
                raise ValueError("at least one of can_lecture or can_assist must be true")
        return self


class StaffCourseRead(StaffCourseBase):
    model_config = ConfigDict(from_attributes=True, extra="forbid")

    id: int = Field(..., gt=0)
    is_active: bool
