from pydantic import BaseModel, ConfigDict, Field


class StudyProgramBase(BaseModel):
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)

    faculty_id: int = Field(..., gt=0)
    level_id: int = Field(..., gt=0)
    code: str = Field(..., min_length=1, max_length=30)
    name: str = Field(..., min_length=1, max_length=150)


class StudyProgramCreate(StudyProgramBase):
    is_active: bool = True


class StudyProgramUpdate(BaseModel):
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)

    faculty_id: int | None = Field(default=None, gt=0)
    level_id: int | None = Field(default=None, gt=0)
    code: str | None = Field(default=None, min_length=1, max_length=30)
    name: str | None = Field(default=None, min_length=1, max_length=150)
    is_active: bool | None = None


class StudyProgramRead(StudyProgramBase):
    model_config = ConfigDict(from_attributes=True, extra="forbid")

    id: int = Field(..., gt=0)
    is_active: bool
