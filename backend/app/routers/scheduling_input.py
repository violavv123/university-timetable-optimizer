from typing import Annotated, Any

from app.models.enums import ComponentType, CourseOfferingStatus, DayOfWeek
from app.routers.crud import register_crud_routes
from app.routers.dependencies import DbSession, Pagination
from app.schemas.common import MessageResponse, PaginatedResponse
from app.schemas.course_offering import (
    CourseOfferingCreate,
    CourseOfferingRead,
    CourseOfferingUpdate,
)
from app.schemas.course_session import CourseSessionCreate, CourseSessionRead, CourseSessionUpdate
from app.schemas.course_session_dependency import (
    CourseSessionDependencyCreate,
    CourseSessionDependencyRead,
    CourseSessionDependencyUpdate,
)
from app.schemas.course_session_group import CourseSessionGroupCreate, CourseSessionGroupRead
from app.schemas.course_session_staff import (
    CourseSessionStaffCreate,
    CourseSessionStaffRead,
    CourseSessionStaffUpdate,
)
from app.schemas.course_session_time_constraint import (
    CourseSessionTimeConstraintCreate,
    CourseSessionTimeConstraintRead,
    CourseSessionTimeConstraintUpdate,
)
from app.schemas.scheduling_profile import (
    SchedulingProfileCreate,
    SchedulingProfileRead,
    SchedulingProfileUpdate,
)
from app.schemas.time_slot import TimeSlotCreate, TimeSlotRead, TimeSlotUpdate
from app.services.scheduling_input import (
    course_offering,
    course_session,
    scheduling_profile,
    time_slot,
)
from app.services.scheduling_input import course_session_dependency as dependency_service
from app.services.scheduling_input import course_session_group as group_service
from app.services.scheduling_input import course_session_staff as staff_service
from app.services.scheduling_input import (
    course_session_time_constraint as time_constraint_service,
)
from fastapi import APIRouter, Depends, Path, status
from pydantic import BaseModel, ConfigDict, Field

router = APIRouter(prefix="/scheduling-input", tags=["Scheduling input"])


class CourseOfferingFilters(BaseModel):
    model_config = ConfigDict(extra="forbid")

    curriculum_course_id: int | None = Field(default=None, gt=0)
    academic_term_id: int | None = Field(default=None, gt=0)
    status: CourseOfferingStatus | None = None


class CourseSessionFilters(BaseModel):
    model_config = ConfigDict(extra="forbid")

    course_offering_id: int | None = Field(default=None, gt=0)
    component_type: ComponentType | None = None
    include_inactive: bool = False


class SessionLinkFilters(BaseModel):
    model_config = ConfigDict(extra="forbid")

    course_session_id: int | None = Field(default=None, gt=0)


class CourseSessionGroupFilters(SessionLinkFilters):
    student_group_id: int | None = Field(default=None, gt=0)


class CourseSessionStaffFilters(SessionLinkFilters):
    staff_member_id: int | None = Field(default=None, gt=0)


class SchedulingProfileFilters(BaseModel):
    model_config = ConfigDict(extra="forbid")

    faculty_id: int | None = Field(default=None, gt=0)
    include_inactive: bool = False


class TimeSlotFilters(BaseModel):
    model_config = ConfigDict(extra="forbid")

    scheduling_profile_id: int | None = Field(default=None, gt=0)
    day_of_week: DayOfWeek | None = None
    include_inactive: bool = False


register_crud_routes(
    router,
    path="/course-offerings",
    resource_name="course offering",
    read_schema=CourseOfferingRead,
    create_schema=CourseOfferingCreate,
    update_schema=CourseOfferingUpdate,
    get_service=course_offering.get_course_offering,
    list_service=course_offering.list_course_offerings,
    create_service=course_offering.create_course_offering,
    update_service=course_offering.update_course_offering,
    delete_service=course_offering.delete_course_offering,
    filters_schema=CourseOfferingFilters,
)
register_crud_routes(
    router,
    path="/course-sessions",
    resource_name="course session",
    read_schema=CourseSessionRead,
    create_schema=CourseSessionCreate,
    update_schema=CourseSessionUpdate,
    get_service=course_session.get_course_session,
    list_service=course_session.list_course_sessions,
    create_service=course_session.create_course_session,
    update_service=course_session.update_course_session,
    delete_service=course_session.delete_course_session,
    filters_schema=CourseSessionFilters,
)
register_crud_routes(
    router,
    path="/course-session-time-constraints",
    resource_name="course session time constraint",
    read_schema=CourseSessionTimeConstraintRead,
    create_schema=CourseSessionTimeConstraintCreate,
    update_schema=CourseSessionTimeConstraintUpdate,
    get_service=time_constraint_service.get_course_session_time_constraint,
    list_service=time_constraint_service.list_course_session_time_constraints,
    create_service=time_constraint_service.create_course_session_time_constraint,
    update_service=time_constraint_service.update_course_session_time_constraint,
    delete_service=time_constraint_service.delete_course_session_time_constraint,
    filters_schema=SessionLinkFilters,
)
register_crud_routes(
    router,
    path="/course-session-dependencies",
    resource_name="course session dependency",
    read_schema=CourseSessionDependencyRead,
    create_schema=CourseSessionDependencyCreate,
    update_schema=CourseSessionDependencyUpdate,
    get_service=dependency_service.get_course_session_dependency,
    list_service=dependency_service.list_course_session_dependencies,
    create_service=dependency_service.create_course_session_dependency,
    update_service=dependency_service.update_course_session_dependency,
    delete_service=dependency_service.delete_course_session_dependency,
    filters_schema=SessionLinkFilters,
)
register_crud_routes(
    router,
    path="/scheduling-profiles",
    resource_name="scheduling profile",
    read_schema=SchedulingProfileRead,
    create_schema=SchedulingProfileCreate,
    update_schema=SchedulingProfileUpdate,
    get_service=scheduling_profile.get_scheduling_profile,
    list_service=scheduling_profile.list_scheduling_profiles,
    create_service=scheduling_profile.create_scheduling_profile,
    update_service=scheduling_profile.update_scheduling_profile,
    delete_service=scheduling_profile.delete_scheduling_profile,
    filters_schema=SchedulingProfileFilters,
)
register_crud_routes(
    router,
    path="/time-slots",
    resource_name="time slot",
    read_schema=TimeSlotRead,
    create_schema=TimeSlotCreate,
    update_schema=TimeSlotUpdate,
    get_service=time_slot.get_time_slot,
    list_service=time_slot.list_time_slots,
    create_service=time_slot.create_time_slot,
    update_service=time_slot.update_time_slot,
    delete_service=time_slot.delete_time_slot,
    filters_schema=TimeSlotFilters,
)


@router.post(
    "/course-offerings/{course_offering_id}/validate-readiness",
    response_model=MessageResponse,
    summary="Validate course offering readiness",
)
def validate_offering_readiness(
    db: DbSession,
    course_offering_id: int = Path(..., gt=0),
) -> MessageResponse:
    course_offering.validate_course_offering_readiness(db, course_offering_id)
    return MessageResponse(message="Course offering is ready for scheduling.")


@router.get(
    "/course-session-groups",
    response_model=PaginatedResponse[CourseSessionGroupRead],
)
def list_course_session_groups(
    db: DbSession,
    pagination: Pagination,
    filters: Annotated[CourseSessionGroupFilters, Depends()],
) -> Any:
    return group_service.list_course_session_groups(
        db,
        pagination,
        **filters.model_dump(exclude_none=True),
    )


@router.post(
    "/course-session-groups",
    response_model=CourseSessionGroupRead,
    status_code=status.HTTP_201_CREATED,
)
def create_course_session_group(
    payload: CourseSessionGroupCreate,
    db: DbSession,
) -> Any:
    return group_service.create_course_session_group(db, payload)


@router.get(
    "/course-session-groups/{course_session_id}/{student_group_id}",
    response_model=CourseSessionGroupRead,
)
def get_course_session_group(
    db: DbSession,
    course_session_id: int = Path(..., gt=0),
    student_group_id: int = Path(..., gt=0),
) -> Any:
    return group_service.get_course_session_group(db, course_session_id, student_group_id)


@router.delete(
    "/course-session-groups/{course_session_id}/{student_group_id}",
    response_model=MessageResponse,
)
def delete_course_session_group(
    db: DbSession,
    course_session_id: int = Path(..., gt=0),
    student_group_id: int = Path(..., gt=0),
) -> MessageResponse:
    return group_service.delete_course_session_group(db, course_session_id, student_group_id)


@router.get(
    "/course-session-staff",
    response_model=PaginatedResponse[CourseSessionStaffRead],
)
def list_course_session_staff(
    db: DbSession,
    pagination: Pagination,
    filters: Annotated[CourseSessionStaffFilters, Depends()],
) -> Any:
    return staff_service.list_course_session_staff(
        db,
        pagination,
        **filters.model_dump(exclude_none=True),
    )


@router.post(
    "/course-session-staff",
    response_model=CourseSessionStaffRead,
    status_code=status.HTTP_201_CREATED,
)
def create_course_session_staff(
    payload: CourseSessionStaffCreate,
    db: DbSession,
) -> Any:
    return staff_service.create_course_session_staff(db, payload)


@router.get(
    "/course-session-staff/{course_session_id}/{staff_member_id}",
    response_model=CourseSessionStaffRead,
)
def get_course_session_staff(
    db: DbSession,
    course_session_id: int = Path(..., gt=0),
    staff_member_id: int = Path(..., gt=0),
) -> Any:
    return staff_service.get_course_session_staff(db, course_session_id, staff_member_id)


@router.patch(
    "/course-session-staff/{course_session_id}/{staff_member_id}",
    response_model=CourseSessionStaffRead,
)
def update_course_session_staff(
    payload: CourseSessionStaffUpdate,
    db: DbSession,
    course_session_id: int = Path(..., gt=0),
    staff_member_id: int = Path(..., gt=0),
) -> Any:
    return staff_service.update_course_session_staff(
        db,
        course_session_id,
        staff_member_id,
        payload,
    )


@router.delete(
    "/course-session-staff/{course_session_id}/{staff_member_id}",
    response_model=MessageResponse,
)
def delete_course_session_staff(
    db: DbSession,
    course_session_id: int = Path(..., gt=0),
    staff_member_id: int = Path(..., gt=0),
) -> MessageResponse:
    return staff_service.delete_course_session_staff(db, course_session_id, staff_member_id)


__all__ = ["router"]
