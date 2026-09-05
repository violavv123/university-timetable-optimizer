from dataclasses import dataclass
from datetime import time
from uuid import uuid4

from app.models.course_offering import CourseOffering
from app.models.course_session import CourseSession
from app.models.course_session_dependency import CourseSessionDependency
from app.models.course_session_group import CourseSessionGroup
from app.models.course_session_staff import CourseSessionStaff
from app.models.course_session_time_constraint import (
    CourseSessionTimeConstraint,
)
from app.models.curriculum_course import CurriculumCourse
from app.models.enums import (
    ComponentType,
    CourseOfferingStatus,
    DayOfWeek,
    DependencyType,
    RoomType,
    TeachingRole,
    TimeConstraintType,
)
from app.models.room import Room
from app.models.scheduling_profile import SchedulingProfile
from app.models.staff_course import StaffCourse
from app.models.staff_member import StaffMember
from app.models.student_group import StudentGroup
from app.models.time_slot import TimeSlot
from app.schemas.course_offering import CourseOfferingCreate
from app.schemas.course_session import CourseSessionCreate
from app.schemas.course_session_dependency import CourseSessionDependencyCreate
from app.schemas.course_session_group import CourseSessionGroupCreate
from app.schemas.course_session_staff import CourseSessionStaffCreate
from app.schemas.course_session_time_constraint import (
    CourseSessionTimeConstraintCreate,
)
from app.schemas.scheduling_profile import SchedulingProfileCreate
from app.schemas.time_slot import TimeSlotCreate
from app.services.scheduling_input.course_offering import create_course_offering
from app.services.scheduling_input.course_session import create_course_session
from app.services.scheduling_input.course_session_dependency import (
    create_course_session_dependency,
)
from app.services.scheduling_input.course_session_group import (
    create_course_session_group,
)
from app.services.scheduling_input.course_session_staff import (
    create_course_session_staff,
)
from app.services.scheduling_input.course_session_time_constraint import (
    create_course_session_time_constraint,
)
from app.services.scheduling_input.scheduling_profile import (
    create_scheduling_profile,
)
from app.services.scheduling_input.time_slot import create_time_slot
from sqlalchemy.orm import Session
from tests.services.academic.factories import (
    AcademicHierarchy,
    make_academic_term,
    make_academic_year,
    make_course,
    make_curriculum_course,
    make_faculty,
    make_level,
    make_program_semester,
    make_study_program,
)
from tests.services.resources.factories import (
    ResourceContext,
    make_resource_context,
    make_room,
    make_staff_course,
    make_staff_member,
    make_student_group,
)


@dataclass(frozen=True)
class SchedulingContext:
    resources: ResourceContext
    curriculum_course: CurriculumCourse
    profile: SchedulingProfile
    offering: CourseOffering
    room: Room
    staff_member: StaffMember
    staff_course: StaffCourse
    cohort: StudentGroup


def make_scheduling_profile(
    db: Session,
    faculty_id: int,
    *,
    name: str | None = None,
    slot_minutes: int = 45,
) -> SchedulingProfile:
    return create_scheduling_profile(
        db,
        SchedulingProfileCreate(
            faculty_id=faculty_id,
            name=name or f"Profile {uuid4().hex[:8]}",
            slot_minutes=slot_minutes,
            max_lecture_students=80,
            max_numerical_students=40,
            max_lab_students=30,
            preferred_room_weight=1,
            historical_room_weight=1,
            student_gap_weight=1,
            staff_gap_weight=1,
            late_hour_weight=1,
            is_active=True,
        ),
    )


def make_time_slot(
    db: Session,
    profile: SchedulingProfile,
    *,
    slot_index: int = 0,
    start_time: time = time(8, 0),
    end_time: time = time(8, 45),
    day_of_week: DayOfWeek = DayOfWeek.MONDAY,
) -> TimeSlot:
    return create_time_slot(
        db,
        TimeSlotCreate(
            scheduling_profile_id=profile.id,
            day_of_week=day_of_week,
            slot_index=slot_index,
            start_time=start_time,
            end_time=end_time,
            is_active=True,
        ),
    )


def make_course_offering(
    db: Session,
    curriculum_course: CurriculumCourse,
    academic_term_id: int,
    *,
    expected_students: int | None = 30,
) -> CourseOffering:
    return create_course_offering(
        db,
        CourseOfferingCreate(
            curriculum_course_id=curriculum_course.id,
            academic_term_id=academic_term_id,
            expected_students=expected_students,
            status=CourseOfferingStatus.DRAFT,
        ),
    )


def _build_context(
    db: Session,
    resources: ResourceContext,
    *,
    lecture_periods: int,
    numerical_periods: int,
    laboratory_periods: int,
    room_type: RoomType,
) -> SchedulingContext:
    curriculum_course = make_curriculum_course(
        db,
        resources.hierarchy.semesters[0],
        resources.course,
        lecture_periods_per_week=lecture_periods,
        numerical_periods_per_week=numerical_periods,
        laboratory_periods_per_week=laboratory_periods,
    )
    profile = make_scheduling_profile(
        db,
        resources.hierarchy.faculty.id,
    )
    offering = make_course_offering(
        db,
        curriculum_course,
        resources.academic_term.id,
    )
    room = make_room(
        db,
        resources.hierarchy.faculty.id,
        room_type=room_type,
    )
    staff_member = make_staff_member(
        db,
        resources.hierarchy.faculty.id,
    )
    staff_course = make_staff_course(
        db,
        staff_member,
        resources.course,
        can_lecture=True,
        can_assist=True,
    )
    cohort = make_student_group(db, resources, student_count=30)
    return SchedulingContext(
        resources,
        curriculum_course,
        profile,
        offering,
        room,
        staff_member,
        staff_course,
        cohort,
    )


def make_scheduling_context(
    db: Session,
    *,
    lecture_periods: int = 2,
    numerical_periods: int = 0,
    laboratory_periods: int = 0,
    room_type: RoomType = RoomType.GENERAL_ROOM,
) -> SchedulingContext:
    return _build_context(
        db,
        make_resource_context(db),
        lecture_periods=lecture_periods,
        numerical_periods=numerical_periods,
        laboratory_periods=laboratory_periods,
        room_type=room_type,
    )


def make_master_scheduling_context(db: Session) -> SchedulingContext:
    faculty = make_faculty(db)
    level = make_level(db, semester_count=4, code="MSC")
    program = make_study_program(db, faculty, level)
    semester = make_program_semester(db, program, 1)
    academic_year = make_academic_year(db)
    term = make_academic_term(db, academic_year)
    course = make_course(db)
    resources = ResourceContext(
        AcademicHierarchy(faculty, level, program, (semester,)),
        term,
        course,
    )
    return _build_context(
        db,
        resources,
        lecture_periods=2,
        numerical_periods=0,
        laboratory_periods=0,
        room_type=RoomType.GENERAL_ROOM,
    )


def make_course_session(
    db: Session,
    context: SchedulingContext,
    *,
    name: str | None = None,
    component_type: ComponentType = ComponentType.LECTURE,
    weekly_frequency: int = 1,
    duration_slots: int = 2,
    max_students: int | None = 40,
    required_room_type: RoomType | None = None,
    required_room_id: int | None = None,
    is_splittable: bool = False,
) -> CourseSession:
    return create_course_session(
        db,
        CourseSessionCreate(
            course_offering_id=context.offering.id,
            name=name or f"Session {uuid4().hex[:8]}",
            component_type=component_type,
            weekly_frequency=weekly_frequency,
            duration_slots=duration_slots,
            max_students=max_students,
            required_room_type=required_room_type,
            required_room_id=required_room_id,
            is_splittable=is_splittable,
            is_active=True,
        ),
    )


def attach_group(
    db: Session,
    session: CourseSession,
    group: StudentGroup,
) -> CourseSessionGroup:
    return create_course_session_group(
        db,
        CourseSessionGroupCreate(
            course_session_id=session.id,
            student_group_id=group.id,
        ),
    )


def attach_staff(
    db: Session,
    session: CourseSession,
    staff_member: StaffMember,
    *,
    teaching_role: TeachingRole | None = None,
    is_primary: bool = True,
) -> CourseSessionStaff:
    roles = {
        ComponentType.LECTURE: TeachingRole.LECTURER,
        ComponentType.NUMERICAL: TeachingRole.NUMERICAL_INSTRUCTOR,
        ComponentType.LABORATORY: TeachingRole.LAB_INSTRUCTOR,
    }
    return create_course_session_staff(
        db,
        CourseSessionStaffCreate(
            course_session_id=session.id,
            staff_member_id=staff_member.id,
            teaching_role=teaching_role or roles[session.component_type],
            is_primary=is_primary,
            is_fixed=True,
        ),
    )


def make_time_constraint(
    db: Session,
    session: CourseSession,
    *,
    constraint_type: TimeConstraintType,
    start_time: time,
    end_time: time,
    day_of_week: DayOfWeek | None = None,
    preference_weight: int | None = None,
) -> CourseSessionTimeConstraint:
    return create_course_session_time_constraint(
        db,
        CourseSessionTimeConstraintCreate(
            course_session_id=session.id,
            day_of_week=day_of_week,
            start_time=start_time,
            end_time=end_time,
            constraint_type=constraint_type,
            preference_weight=preference_weight,
        ),
    )


def make_dependency(
    db: Session,
    predecessor: CourseSession,
    successor: CourseSession,
    *,
    dependency_type: DependencyType = DependencyType.PRECEDES,
    min_gap_slots: int | None = None,
    max_gap_slots: int | None = None,
) -> CourseSessionDependency:
    return create_course_session_dependency(
        db,
        CourseSessionDependencyCreate(
            predecessor_session_id=predecessor.id,
            successor_session_id=successor.id,
            dependency_type=dependency_type,
            min_gap_slots=min_gap_slots,
            max_gap_slots=max_gap_slots,
        ),
    )
