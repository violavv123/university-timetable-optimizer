from pydantic import BaseModel, ConfigDict, Field


class ProgramSemesterBase(BaseModel):
    model_config = ConfigDict(extra="forbid")

    study_program_id: int = Field(..., gt=0)
    semester_number: int = Field(..., gt=0, le=32767)


class ProgramSemesterCreate(ProgramSemesterBase):
    is_active: bool = True


class ProgramSemesterUpdate(BaseModel):
    model_config = ConfigDict(extra="forbid")

    study_program_id: int | None = Field(default=None, gt=0)
    semester_number: int | None = Field(default=None, gt=0, le=32767)
    is_active: bool | None = None


class ProgramSemesterRead(ProgramSemesterBase):
    model_config = ConfigDict(from_attributes=True, extra="forbid")

    id: int = Field(..., gt=0)
    is_active: bool
