from pydantic import BaseModel, ConfigDict, Field

from app.models.enums import TeachingRole


class CourseSessionStaffBase(BaseModel):
    model_config = ConfigDict(extra="forbid")

    course_session_id: int = Field(..., gt=0)
    staff_member_id: int = Field(..., gt=0)
    teaching_role: TeachingRole
    is_primary: bool = False
    is_fixed: bool = True


class CourseSessionStaffCreate(CourseSessionStaffBase):
    pass


class CourseSessionStaffUpdate(BaseModel):
    """Only mutable assignment attributes are patchable; composite keys are immutable."""

    model_config = ConfigDict(extra="forbid")

    teaching_role: TeachingRole | None = None
    is_primary: bool | None = None
    is_fixed: bool | None = None


class CourseSessionStaffRead(CourseSessionStaffBase):
    model_config = ConfigDict(from_attributes=True, extra="forbid")
