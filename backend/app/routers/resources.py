from app.models.enums import RoomStatus, RoomType
from app.routers.crud import register_crud_routes
from app.schemas.program_room_preference import (
    ProgramRoomPreferenceCreate,
    ProgramRoomPreferenceRead,
    ProgramRoomPreferenceUpdate,
)
from app.schemas.room import RoomCreate, RoomRead, RoomUpdate
from app.schemas.room_availability import (
    RoomAvailabilityCreate,
    RoomAvailabilityRead,
    RoomAvailabilityUpdate,
)
from app.schemas.staff_availability import (
    StaffAvailabilityCreate,
    StaffAvailabilityRead,
    StaffAvailabilityUpdate,
)
from app.schemas.staff_course import StaffCourseCreate, StaffCourseRead, StaffCourseUpdate
from app.schemas.staff_member import StaffMemberCreate, StaffMemberRead, StaffMemberUpdate
from app.schemas.student_group import StudentGroupCreate, StudentGroupRead, StudentGroupUpdate
from app.services.resources import (
    program_room_preference,
    room,
    room_availability,
    staff_availability,
    staff_course,
    staff_member,
    student_group,
)
from fastapi import APIRouter
from pydantic import BaseModel, ConfigDict, Field

router = APIRouter(prefix="/resources", tags=["Resources"])


class StaffMemberFilters(BaseModel):
    model_config = ConfigDict(extra="forbid")

    faculty_id: int | None = Field(default=None, gt=0)
    include_inactive: bool = False


class StaffCourseFilters(BaseModel):
    model_config = ConfigDict(extra="forbid")

    staff_member_id: int | None = Field(default=None, gt=0)
    course_id: int | None = Field(default=None, gt=0)
    include_inactive: bool = False


class AvailabilityFilters(BaseModel):
    model_config = ConfigDict(extra="forbid")

    academic_term_id: int | None = Field(default=None, gt=0)


class StaffAvailabilityFilters(AvailabilityFilters):
    staff_member_id: int | None = Field(default=None, gt=0)


class StudentGroupFilters(BaseModel):
    model_config = ConfigDict(extra="forbid")

    program_semester_id: int | None = Field(default=None, gt=0)
    academic_term_id: int | None = Field(default=None, gt=0)
    parent_group_id: int | None = Field(default=None, gt=0)
    include_inactive: bool = False


class RoomFilters(BaseModel):
    model_config = ConfigDict(extra="forbid")

    faculty_id: int | None = Field(default=None, gt=0)
    room_type: RoomType | None = None
    status: RoomStatus | None = None
    include_unavailable: bool = False


class RoomAvailabilityFilters(AvailabilityFilters):
    room_id: int | None = Field(default=None, gt=0)


class ProgramRoomPreferenceFilters(BaseModel):
    model_config = ConfigDict(extra="forbid")

    study_program_id: int | None = Field(default=None, gt=0)
    room_id: int | None = Field(default=None, gt=0)
    include_inactive: bool = False


register_crud_routes(
    router,
    path="/staff-members",
    resource_name="staff member",
    read_schema=StaffMemberRead,
    create_schema=StaffMemberCreate,
    update_schema=StaffMemberUpdate,
    get_service=staff_member.get_staff_member,
    list_service=staff_member.list_staff_members,
    create_service=staff_member.create_staff_member,
    update_service=staff_member.update_staff_member,
    delete_service=staff_member.delete_staff_member,
    filters_schema=StaffMemberFilters,
)
register_crud_routes(
    router,
    path="/staff-courses",
    resource_name="staff course",
    read_schema=StaffCourseRead,
    create_schema=StaffCourseCreate,
    update_schema=StaffCourseUpdate,
    get_service=staff_course.get_staff_course,
    list_service=staff_course.list_staff_courses,
    create_service=staff_course.create_staff_course,
    update_service=staff_course.update_staff_course,
    delete_service=staff_course.delete_staff_course,
    filters_schema=StaffCourseFilters,
)
register_crud_routes(
    router,
    path="/staff-availability",
    resource_name="staff availability",
    read_schema=StaffAvailabilityRead,
    create_schema=StaffAvailabilityCreate,
    update_schema=StaffAvailabilityUpdate,
    get_service=staff_availability.get_staff_availability,
    list_service=staff_availability.list_staff_availabilities,
    create_service=staff_availability.create_staff_availability,
    update_service=staff_availability.update_staff_availability,
    delete_service=staff_availability.delete_staff_availability,
    filters_schema=StaffAvailabilityFilters,
)
register_crud_routes(
    router,
    path="/student-groups",
    resource_name="student group",
    read_schema=StudentGroupRead,
    create_schema=StudentGroupCreate,
    update_schema=StudentGroupUpdate,
    get_service=student_group.get_student_group,
    list_service=student_group.list_student_groups,
    create_service=student_group.create_student_group,
    update_service=student_group.update_student_group,
    delete_service=student_group.delete_student_group,
    filters_schema=StudentGroupFilters,
)
register_crud_routes(
    router,
    path="/rooms",
    resource_name="room",
    read_schema=RoomRead,
    create_schema=RoomCreate,
    update_schema=RoomUpdate,
    get_service=room.get_room,
    list_service=room.list_rooms,
    create_service=room.create_room,
    update_service=room.update_room,
    delete_service=room.delete_room,
    filters_schema=RoomFilters,
)
register_crud_routes(
    router,
    path="/room-availability",
    resource_name="room availability",
    read_schema=RoomAvailabilityRead,
    create_schema=RoomAvailabilityCreate,
    update_schema=RoomAvailabilityUpdate,
    get_service=room_availability.get_room_availability,
    list_service=room_availability.list_room_availabilities,
    create_service=room_availability.create_room_availability,
    update_service=room_availability.update_room_availability,
    delete_service=room_availability.delete_room_availability,
    filters_schema=RoomAvailabilityFilters,
)
register_crud_routes(
    router,
    path="/program-room-preferences",
    resource_name="program room preference",
    read_schema=ProgramRoomPreferenceRead,
    create_schema=ProgramRoomPreferenceCreate,
    update_schema=ProgramRoomPreferenceUpdate,
    get_service=program_room_preference.get_program_room_preference,
    list_service=program_room_preference.list_program_room_preferences,
    create_service=program_room_preference.create_program_room_preference,
    update_service=program_room_preference.update_program_room_preference,
    delete_service=program_room_preference.delete_program_room_preference,
    filters_schema=ProgramRoomPreferenceFilters,
)


__all__ = ["router"]
