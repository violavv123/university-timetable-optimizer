from pydantic import BaseModel, ConfigDict, Field


class FacultyBase(BaseModel):
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)

    code: str = Field(..., min_length=1, max_length=30)
    name: str = Field(..., min_length=1, max_length=150)


class FacultyCreate(FacultyBase):
    is_active: bool = True


class FacultyUpdate(BaseModel):
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)

    code: str | None = Field(default=None, min_length=1, max_length=30)
    name: str | None = Field(default=None, min_length=1, max_length=150)
    is_active: bool | None = None


class FacultyRead(FacultyBase):
    model_config = ConfigDict(from_attributes=True, extra="forbid")

    id: int = Field(..., gt=0)
    is_active: bool
