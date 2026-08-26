from pydantic import BaseModel, ConfigDict, Field


class LevelBase(BaseModel):
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)

    code: str = Field(..., min_length=1, max_length=20)
    name: str = Field(..., min_length=1, max_length=100)
    semester_count: int = Field(..., gt=0, le=32767)


class LevelCreate(LevelBase):
    is_active: bool = True


class LevelUpdate(BaseModel):
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)

    code: str | None = Field(default=None, min_length=1, max_length=20)
    name: str | None = Field(default=None, min_length=1, max_length=100)
    semester_count: int | None = Field(default=None, gt=0, le=32767)
    is_active: bool | None = None


class LevelRead(LevelBase):
    model_config = ConfigDict(from_attributes=True, extra="forbid")

    id: int = Field(..., gt=0)
    is_active: bool
