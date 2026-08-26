from pydantic import BaseModel, ConfigDict, Field

from app.models.enums import StudentGroupType


class StudentGroupBase(BaseModel):
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)

    program_semester_id: int = Field(..., gt=0)
    academic_term_id: int = Field(..., gt=0)
    parent_group_id: int | None = Field(default=None, gt=0)
    name: str = Field(..., min_length=1, max_length=100)
    group_type: StudentGroupType
    student_count: int = Field(..., gt=0)


class StudentGroupCreate(StudentGroupBase):
    is_active: bool = True


class StudentGroupUpdate(BaseModel):
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)

    program_semester_id: int | None = Field(default=None, gt=0)
    academic_term_id: int | None = Field(default=None, gt=0)
    parent_group_id: int | None = Field(default=None, gt=0)
    name: str | None = Field(default=None, min_length=1, max_length=100)
    group_type: StudentGroupType | None = None
    student_count: int | None = Field(default=None, gt=0)
    is_active: bool | None = None


class StudentGroupRead(StudentGroupBase):
    model_config = ConfigDict(from_attributes=True, extra="forbid")

    id: int = Field(..., gt=0)
    is_active: bool
