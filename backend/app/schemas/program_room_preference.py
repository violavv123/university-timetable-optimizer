from pydantic import BaseModel, ConfigDict, Field


class ProgramRoomPreferenceBase(BaseModel):
    model_config = ConfigDict(extra="forbid")

    study_program_id: int = Field(..., gt=0)
    room_id: int = Field(..., gt=0)
    penalty_weight: int = Field(default=1, ge=0, le=32767)


class ProgramRoomPreferenceCreate(ProgramRoomPreferenceBase):
    is_active: bool = True


class ProgramRoomPreferenceUpdate(BaseModel):
    model_config = ConfigDict(extra="forbid")

    study_program_id: int | None = Field(default=None, gt=0)
    room_id: int | None = Field(default=None, gt=0)
    penalty_weight: int | None = Field(default=None, ge=0, le=32767)
    is_active: bool | None = None


class ProgramRoomPreferenceRead(ProgramRoomPreferenceBase):
    model_config = ConfigDict(from_attributes=True, extra="forbid")

    id: int = Field(..., gt=0)
    is_active: bool
