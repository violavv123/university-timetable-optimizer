from app.models.enums import RoomStatus, RoomType
from pydantic import BaseModel, ConfigDict, Field


class RoomBase(BaseModel):
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)

    faculty_id: int = Field(..., gt=0)
    code: str = Field(..., min_length=1, max_length=30)
    name: str = Field(..., min_length=1, max_length=150)
    capacity: int = Field(..., gt=0)
    room_type: RoomType


class RoomCreate(RoomBase):
    status: RoomStatus = RoomStatus.ACTIVE


class RoomUpdate(BaseModel):
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)

    faculty_id: int | None = Field(default=None, gt=0)
    code: str | None = Field(default=None, min_length=1, max_length=30)
    name: str | None = Field(default=None, min_length=1, max_length=150)
    capacity: int | None = Field(default=None, gt=0)
    room_type: RoomType | None = None
    status: RoomStatus | None = None


class RoomRead(RoomBase):
    model_config = ConfigDict(from_attributes=True, extra="forbid")

    id: int = Field(..., gt=0)
    status: RoomStatus
