from pydantic import BaseModel, ConfigDict, Field


class CourseBase(BaseModel):
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)

    code: str = Field(..., min_length=1, max_length=30)
    name: str = Field(..., min_length=1, max_length=200)


class CourseCreate(CourseBase):
    is_active: bool = True


class CourseUpdate(BaseModel):
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)

    code: str | None = Field(default=None, min_length=1, max_length=30)
    name: str | None = Field(default=None, min_length=1, max_length=200)
    is_active: bool | None = None


class CourseRead(CourseBase):
    model_config = ConfigDict(from_attributes=True, extra="forbid")

    id: int = Field(..., gt=0)
    is_active: bool
