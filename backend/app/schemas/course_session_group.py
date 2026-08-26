from pydantic import BaseModel, ConfigDict, Field


class CourseSessionGroupCreate(BaseModel):
    model_config = ConfigDict(extra="forbid")

    course_session_id: int = Field(..., gt=0)
    student_group_id: int = Field(..., gt=0)


class CourseSessionGroupRead(CourseSessionGroupCreate):
    model_config = ConfigDict(from_attributes=True, extra="forbid")
