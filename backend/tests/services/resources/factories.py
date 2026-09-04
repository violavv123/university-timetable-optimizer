from dataclasses import dataclass
from datetime import time
from uuid import uuid4

from app.models.academic_term import AcademicTerm
from app.models.course import Course
from app.models.enums import (
    AcademicTitle,
    AvailabilityType,
    DayOfWeek,
    RoomStatus,
    RoomType,
    StaffType,
    StudentGroupType,
)
from app.models.program_room_preference import ProgramRoomPreference
from app.models.room import Room
from app.models.room_availability import RoomAvailability
from app.models.staff_availability import StaffAvailability
from app.models.staff_course import StaffCourse
from app.models.staff_member import StaffMember
from app.models.student_group import StudentGroup
from app.schemas.program_room_preference import ProgramRoomPreferenceCreate
from app.schemas.room import RoomCreate
from app.schemas.room_availability import RoomAvailabilityCreate
from app.schemas.staff_availability import StaffAvailabilityCreate
from app.schemas.staff_course import StaffCourseCreate
from app.schemas.staff_member import StaffMemberCreate
from app.schemas.student_group import StudentGroupCreate
from app.services.resources.program_room_preference import (
    create_program_room_preference,
)
from app.services.resources.room import create_room
from app.services.resources.room_availability import create_room_availability
from app.services.resources.staff_availability import create_staff_availability
from app.services.resources.staff_course import create_staff_course
from app.services.resources.staff_member import create_staff_member
from app.services.resources.student_group import create_student_group
from sqlalchemy.orm import Session
from tests.services.academic.factories import (
    AcademicHierarchy,
    make_academic_term,
    make_academic_year,
    make_course,
    make_hierarchy,
    unique_code,
)


@dataclass(frozen=True)
class ResourceContext:
    hierarchy: AcademicHierarchy
    academic_term: AcademicTerm
    course: Course


def make_resource_context(db: Session) -> ResourceContext:
    hierarchy = make_hierarchy(db, created_semesters=(1,))
    academic_year = make_academic_year(db)
    academic_term = make_academic_term(db, academic_year)
    course = make_course(db)
    return ResourceContext(hierarchy, academic_term, course)


def unique_email() -> str:
    return f"staff-{uuid4().hex[:10]}@example.test"


def make_staff_member(
    db: Session,
    faculty_id: int,
    *,
    email: str | None = None,
    is_active: bool = True,
) -> StaffMember:
    return create_staff_member(
        db,
        StaffMemberCreate(
            faculty_id=faculty_id,
            first_name="Test",
            last_name="Lecturer",
            email=email if email is not None else unique_email(),
            academic_title=AcademicTitle.ASSISTANT_PROFESSOR,
            staff_type=StaffType.INTERNAL,
            is_active=is_active,
        ),
    )


def make_staff_course(
    db: Session,
    staff_member: StaffMember,
    course: Course,
    *,
    can_lecture: bool = True,
    can_assist: bool = False,
    is_active: bool = True,
) -> StaffCourse:
    return create_staff_course(
        db,
        StaffCourseCreate(
            staff_member_id=staff_member.id,
            course_id=course.id,
            can_lecture=can_lecture,
            can_assist=can_assist,
            is_active=is_active,
        ),
    )


def make_room(
    db: Session,
    faculty_id: int,
    *,
    capacity: int = 40,
    room_type: RoomType = RoomType.GENERAL_ROOM,
    status: RoomStatus = RoomStatus.ACTIVE,
    code: str | None = None,
) -> Room:
    room_code = code or unique_code("ROOM")
    return create_room(
        db,
        RoomCreate(
            faculty_id=faculty_id,
            code=room_code,
            name=f"Test room {room_code}",
            capacity=capacity,
            room_type=room_type,
            status=status,
        ),
    )


def make_staff_availability(
    db: Session,
    staff_member: StaffMember,
    academic_term: AcademicTerm,
    *,
    start_time: time = time(9, 0),
    end_time: time = time(11, 0),
    availability_type: AvailabilityType = AvailabilityType.AVAILABLE,
    preference_weight: int | None = None,
) -> StaffAvailability:
    return create_staff_availability(
        db,
        StaffAvailabilityCreate(
            staff_member_id=staff_member.id,
            academic_term_id=academic_term.id,
            day_of_week=DayOfWeek.MONDAY,
            start_time=start_time,
            end_time=end_time,
            availability_type=availability_type,
            preference_weight=preference_weight,
        ),
    )


def make_room_availability(
    db: Session,
    room: Room,
    academic_term: AcademicTerm,
    *,
    start_time: time = time(9, 0),
    end_time: time = time(11, 0),
    availability_type: AvailabilityType = AvailabilityType.AVAILABLE,
    preference_weight: int | None = None,
) -> RoomAvailability:
    return create_room_availability(
        db,
        RoomAvailabilityCreate(
            room_id=room.id,
            academic_term_id=academic_term.id,
            day_of_week=DayOfWeek.MONDAY,
            start_time=start_time,
            end_time=end_time,
            availability_type=availability_type,
            preference_weight=preference_weight,
        ),
    )


def make_student_group(
    db: Session,
    context: ResourceContext,
    *,
    name: str | None = None,
    group_type: StudentGroupType = StudentGroupType.COHORT,
    student_count: int = 30,
    parent_group: StudentGroup | None = None,
    is_active: bool = True,
) -> StudentGroup:
    return create_student_group(
        db,
        StudentGroupCreate(
            program_semester_id=context.hierarchy.semesters[0].id,
            academic_term_id=context.academic_term.id,
            parent_group_id=parent_group.id if parent_group else None,
            name=name or f"Group {uuid4().hex[:8]}",
            group_type=group_type,
            student_count=student_count,
            is_active=is_active,
        ),
    )


def make_program_room_preference(
    db: Session,
    context: ResourceContext,
    room: Room,
    *,
    penalty_weight: int = 1,
    is_active: bool = True,
) -> ProgramRoomPreference:
    return create_program_room_preference(
        db,
        ProgramRoomPreferenceCreate(
            study_program_id=context.hierarchy.study_program.id,
            room_id=room.id,
            penalty_weight=penalty_weight,
            is_active=is_active,
        ),
    )
