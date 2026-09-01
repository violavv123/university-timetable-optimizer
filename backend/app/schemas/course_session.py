from app.models.enums import ComponentType, RoomType
from pydantic import BaseModel, ConfigDict, Field


class CourseSessionBase(BaseModel):
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)

    course_offering_id: int = Field(..., gt=0)
    name: str = Field(..., min_length=1, max_length=150)
    component_type: ComponentType
    weekly_frequency: int = Field(default=1, gt=0, le=32767)
    duration_slots: int = Field(..., gt=0, le=32767)
    max_students: int | None = Field(default=None, gt=0)
    required_room_type: RoomType | None = None
    required_room_id: int | None = Field(default=None, gt=0)
    is_splittable: bool = False


class CourseSessionCreate(CourseSessionBase):
    is_active: bool = True


class CourseSessionUpdate(BaseModel):
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)

    course_offering_id: int | None = Field(default=None, gt=0)
    name: str | None = Field(default=None, min_length=1, max_length=150)
    component_type: ComponentType | None = None
    weekly_frequency: int | None = Field(default=None, gt=0, le=32767)
    duration_slots: int | None = Field(default=None, gt=0, le=32767)
    max_students: int | None = Field(default=None, gt=0)
    required_room_type: RoomType | None = None
    required_room_id: int | None = Field(default=None, gt=0)
    is_splittable: bool | None = None
    is_active: bool | None = None


class CourseSessionRead(CourseSessionBase):
    model_config = ConfigDict(from_attributes=True, extra="forbid")

    id: int = Field(..., gt=0)
    is_active: bool
