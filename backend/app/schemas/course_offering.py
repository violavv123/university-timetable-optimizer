from pydantic import BaseModel, ConfigDict, Field

from app.models.enums import CourseOfferingStatus


class CourseOfferingBase(BaseModel):
    model_config = ConfigDict(extra="forbid")

    curriculum_course_id: int = Field(..., gt=0)
    academic_term_id: int = Field(..., gt=0)
    expected_students: int | None = Field(default=None, gt=0)


class CourseOfferingCreate(CourseOfferingBase):
    status: CourseOfferingStatus = CourseOfferingStatus.DRAFT


class CourseOfferingUpdate(BaseModel):
    model_config = ConfigDict(extra="forbid")

    curriculum_course_id: int | None = Field(default=None, gt=0)
    academic_term_id: int | None = Field(default=None, gt=0)
    expected_students: int | None = Field(default=None, gt=0)
    status: CourseOfferingStatus | None = None


class CourseOfferingRead(CourseOfferingBase):
    model_config = ConfigDict(from_attributes=True, extra="forbid")

    id: int = Field(..., gt=0)
    status: CourseOfferingStatus
