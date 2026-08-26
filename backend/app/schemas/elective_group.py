from pydantic import BaseModel, ConfigDict, Field


class ElectiveGroupBase(BaseModel):
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)

    program_semester_id: int = Field(..., gt=0)
    name: str = Field(..., min_length=1, max_length=150)
    required_choices: int = Field(default=1, gt=0, le=32767)


class ElectiveGroupCreate(ElectiveGroupBase):
    is_active: bool = True


class ElectiveGroupUpdate(BaseModel):
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)

    program_semester_id: int | None = Field(default=None, gt=0)
    name: str | None = Field(default=None, min_length=1, max_length=150)
    required_choices: int | None = Field(default=None, gt=0, le=32767)
    is_active: bool | None = None


class ElectiveGroupRead(ElectiveGroupBase):
    model_config = ConfigDict(from_attributes=True, extra="forbid")

    id: int = Field(..., gt=0)
    is_active: bool
