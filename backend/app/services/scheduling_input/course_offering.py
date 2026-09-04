from datetime import date, time

from app.core.exceptions import (
    BusinessRuleError,
    InvalidReferenceError,
    ResourceInUseError,
)
from app.models.academic_term import AcademicTerm
from app.models.course_offering import CourseOffering
from app.models.course_session import CourseSession
from app.models.course_session_group import CourseSessionGroup
from app.models.course_session_staff import CourseSessionStaff
from app.models.course_session_time_constraint import (
    CourseSessionTimeConstraint,
)
from app.models.curriculum_course import CurriculumCourse
from app.models.enums import (
    ComponentType,
    CourseOfferingStatus,
    TermType,
    TimeConstraintType,
)
from app.models.timetable_entry import TimetableEntry
from app.schemas.common import MessageResponse, PaginatedResponse, PaginationParams
from app.schemas.course_offering import (
    CourseOfferingCreate,
    CourseOfferingRead,
    CourseOfferingUpdate,
)
from app.services.academic.hierarchy import (
    require_active_program_semester_hierarchy,
)
from app.services.common import (
    apply_changes,
    commit_and_refresh,
    ensure_unique,
    paginated_rows,
    require_active,
    require_by_id,
    validated_changes,
)
from sqlalchemy import func, select
from sqlalchemy.orm import Session

ALLOWED_STATUS_TRANSITIONS: dict[
    CourseOfferingStatus,
    set[CourseOfferingStatus],
] = {
    CourseOfferingStatus.DRAFT: {
        CourseOfferingStatus.READY,
        CourseOfferingStatus.CANCELLED,
    },
    CourseOfferingStatus.READY: {
        CourseOfferingStatus.DRAFT,
        CourseOfferingStatus.CANCELLED,
        CourseOfferingStatus.COMPLETED,
    },
    CourseOfferingStatus.CANCELLED: set(),
    CourseOfferingStatus.COMPLETED: set(),
}

MASTER_LEVEL_CODE = "MSC"
MASTER_PREFERRED_START = time(17, 0)
MASTER_LATEST_END = time(20, 0)


def _expected_periods(
    curriculum_course: CurriculumCourse,
    component_type: ComponentType,
) -> int:
    if component_type == ComponentType.LECTURE:
        return curriculum_course.lecture_periods_per_week
    if component_type == ComponentType.NUMERICAL:
        return curriculum_course.numerical_periods_per_week
    return curriculum_course.laboratory_periods_per_week


def _validate_curriculum_and_term(
    db: Session,
    *,
    curriculum_course_id: int,
    academic_term_id: int,
    require_active_parents: bool,
) -> tuple[CurriculumCourse, AcademicTerm]:
    curriculum_course = require_by_id(
        db,
        CurriculumCourse,
        curriculum_course_id,
        "Curriculum course",
    )
    academic_term = require_by_id(
        db,
        AcademicTerm,
        academic_term_id,
        "Academic term",
    )
    program_semester = curriculum_course.program_semester
    expected_term_type = (
        TermType.WINTER if program_semester.semester_number % 2 == 1 else TermType.SUMMER
    )
    if academic_term.term_type != expected_term_type:
        raise InvalidReferenceError(
            "The offering term type is incompatible with the program semester.",
            details={
                "curriculum_course_id": curriculum_course.id,
                "program_semester_id": program_semester.id,
                "semester_number": program_semester.semester_number,
                "expected_term_type": expected_term_type,
                "academic_term_id": academic_term.id,
                "actual_term_type": academic_term.term_type,
            },
        )
    if not curriculum_course.requires_timetable:
        raise BusinessRuleError(
            "A curriculum course with requires_timetable=False cannot have a scheduling offering.",
            details={"curriculum_course_id": curriculum_course.id},
        )
    if require_active_parents:
        require_active_program_semester_hierarchy(program_semester)
        require_active(curriculum_course, "Curriculum course")
        require_active(curriculum_course.course, "Course")
        require_active(academic_term, "Academic term")
    return curriculum_course, academic_term


def _active_sessions(db: Session, course_offering_id: int) -> list[CourseSession]:
    return list(
        db.scalars(
            select(CourseSession).where(
                CourseSession.course_offering_id == course_offering_id,
                CourseSession.is_active.is_(True),
            )
        ).all()
    )


def validate_course_offering_readiness(
    db: Session,
    course_offering_id: int,
) -> None:
    offering = require_by_id(
        db,
        CourseOffering,
        course_offering_id,
        "Course offering",
    )
    curriculum_course, _ = _validate_curriculum_and_term(
        db,
        curriculum_course_id=offering.curriculum_course_id,
        academic_term_id=offering.academic_term_id,
        require_active_parents=True,
    )
    sessions = _active_sessions(db, offering.id)
    if not sessions:
        raise BusinessRuleError(
            "A course offering must have active sessions before it is ready.",
            details={"course_offering_id": offering.id},
        )

    actual_periods: dict[ComponentType, int] = {
        component_type: 0 for component_type in ComponentType
    }
    for session in sessions:
        actual_periods[session.component_type] += session.weekly_frequency * session.duration_slots
        group_count = int(
            db.scalar(
                select(func.count())
                .select_from(CourseSessionGroup)
                .where(CourseSessionGroup.course_session_id == session.id)
            )
            or 0
        )
        if group_count == 0:
            raise BusinessRuleError(
                "Every active session requires at least one student group.",
                details={"course_session_id": session.id},
            )

        staff_count = int(
            db.scalar(
                select(func.count())
                .select_from(CourseSessionStaff)
                .where(CourseSessionStaff.course_session_id == session.id)
            )
            or 0
        )
        if staff_count == 0:
            raise BusinessRuleError(
                "Every active session requires at least one staff assignment.",
                details={"course_session_id": session.id},
            )
        primary_count = int(
            db.scalar(
                select(func.count())
                .select_from(CourseSessionStaff)
                .where(
                    CourseSessionStaff.course_session_id == session.id,
                    CourseSessionStaff.is_primary.is_(True),
                )
            )
            or 0
        )
        if primary_count != 1:
            raise BusinessRuleError(
                "Every active session must have exactly one primary staff member.",
                details={
                    "course_session_id": session.id,
                    "primary_staff_count": primary_count,
                },
            )

        level_code = curriculum_course.program_semester.study_program.level.code
        if level_code.strip().upper() == MASTER_LEVEL_CODE:
            constraints = list(
                db.scalars(
                    select(CourseSessionTimeConstraint).where(
                        CourseSessionTimeConstraint.course_session_id == session.id
                    )
                ).all()
            )
            has_hard_end = any(
                constraint.constraint_type == TimeConstraintType.ALLOWED_WINDOW
                and constraint.day_of_week is None
                and constraint.end_time <= MASTER_LATEST_END
                for constraint in constraints
            )
            has_evening_preference = any(
                constraint.constraint_type == TimeConstraintType.PREFERRED_WINDOW
                and constraint.day_of_week is None
                and constraint.start_time <= MASTER_PREFERRED_START
                and constraint.end_time >= MASTER_LATEST_END
                for constraint in constraints
            )
            if not has_hard_end or not has_evening_preference:
                raise BusinessRuleError(
                    "Master sessions require a latest 20:00 allowed bound "
                    "and a 17:00-20:00 preferred window.",
                    details={"course_session_id": session.id},
                )

    for component_type in ComponentType:
        expected = _expected_periods(curriculum_course, component_type)
        actual = actual_periods[component_type]
        if actual != expected:
            raise BusinessRuleError(
                "Active session periods must exactly match the curriculum course.",
                details={
                    "course_offering_id": offering.id,
                    "component_type": component_type,
                    "expected_periods": expected,
                    "actual_periods": actual,
                },
            )


def _ensure_no_timetable_entries(db: Session, course_offering_id: int) -> None:
    timetable_entry_id = db.scalar(
        select(TimetableEntry.id)
        .join(
            CourseSession,
            CourseSession.id == TimetableEntry.course_session_id,
        )
        .where(CourseSession.course_offering_id == course_offering_id)
        .limit(1)
    )
    if timetable_entry_id is not None:
        raise ResourceInUseError(
            "A course offering with timetable entries cannot be cancelled or reassigned.",
            details={
                "course_offering_id": course_offering_id,
                "timetable_entry_id": timetable_entry_id,
            },
        )


def _validate_status_transition(
    db: Session,
    offering: CourseOffering,
    new_status: CourseOfferingStatus,
) -> None:
    if new_status == offering.status:
        return
    if new_status not in ALLOWED_STATUS_TRANSITIONS[offering.status]:
        raise BusinessRuleError(
            "Invalid course-offering status transition.",
            details={
                "course_offering_id": offering.id,
                "current_status": offering.status,
                "requested_status": new_status,
            },
        )
    if new_status == CourseOfferingStatus.READY:
        validate_course_offering_readiness(db, offering.id)
    if new_status == CourseOfferingStatus.CANCELLED:
        _ensure_no_timetable_entries(db, offering.id)
    if new_status == CourseOfferingStatus.COMPLETED:
        if offering.academic_term.end_date > date.today():
            raise BusinessRuleError(
                "An offering cannot be completed before its academic term ends.",
                details={
                    "course_offering_id": offering.id,
                    "academic_term_end_date": offering.academic_term.end_date,
                },
            )


def get_course_offering(
    db: Session,
    course_offering_id: int,
) -> CourseOffering:
    return require_by_id(
        db,
        CourseOffering,
        course_offering_id,
        "Course offering",
    )


def list_course_offerings(
    db: Session,
    pagination: PaginationParams,
    *,
    curriculum_course_id: int | None = None,
    academic_term_id: int | None = None,
    status: CourseOfferingStatus | None = None,
) -> PaginatedResponse[CourseOfferingRead]:
    filters = []
    if curriculum_course_id is not None:
        require_by_id(
            db,
            CurriculumCourse,
            curriculum_course_id,
            "Curriculum course",
        )
        filters.append(CourseOffering.curriculum_course_id == curriculum_course_id)
    if academic_term_id is not None:
        require_by_id(db, AcademicTerm, academic_term_id, "Academic term")
        filters.append(CourseOffering.academic_term_id == academic_term_id)
    if status is not None:
        filters.append(CourseOffering.status == status)

    statement = (
        select(CourseOffering)
        .where(*filters)
        .order_by(
            CourseOffering.academic_term_id.desc(),
            CourseOffering.curriculum_course_id,
        )
    )
    count_statement = select(func.count()).select_from(CourseOffering).where(*filters)
    rows, total = paginated_rows(db, statement, count_statement, pagination)
    return PaginatedResponse[CourseOfferingRead](
        items=[CourseOfferingRead.model_validate(row) for row in rows],
        total=total,
        page=pagination.page,
        page_size=pagination.page_size,
    )


def create_course_offering(
    db: Session,
    payload: CourseOfferingCreate,
) -> CourseOffering:
    if payload.expected_students is not None and payload.expected_students <= 0:
        raise BusinessRuleError("expected_students must be greater than zero.")
    if payload.status != CourseOfferingStatus.DRAFT:
        raise BusinessRuleError("New course offerings must start in DRAFT status.")
    _validate_curriculum_and_term(
        db,
        curriculum_course_id=payload.curriculum_course_id,
        academic_term_id=payload.academic_term_id,
        require_active_parents=True,
    )
    ensure_unique(
        db,
        CourseOffering,
        "Course offering",
        ["curriculum_course_id", "academic_term_id"],
        CourseOffering.curriculum_course_id == payload.curriculum_course_id,
        CourseOffering.academic_term_id == payload.academic_term_id,
    )

    offering = CourseOffering(**payload.model_dump())
    db.add(offering)
    return commit_and_refresh(db, offering)


def update_course_offering(
    db: Session,
    course_offering_id: int,
    payload: CourseOfferingUpdate,
) -> CourseOffering:
    offering = get_course_offering(db, course_offering_id)
    changes = validated_changes(
        payload,
        non_nullable_fields=(
            "curriculum_course_id",
            "academic_term_id",
            "status",
        ),
    )
    curriculum_course_id = changes.get(
        "curriculum_course_id",
        offering.curriculum_course_id,
    )
    academic_term_id = changes.get(
        "academic_term_id",
        offering.academic_term_id,
    )
    expected_students = changes.get(
        "expected_students",
        offering.expected_students,
    )
    new_status = changes.get("status", offering.status)
    if expected_students is not None and expected_students <= 0:
        raise BusinessRuleError("expected_students must be greater than zero.")

    non_status_changes = set(changes) - {"status"}
    if "status" in changes and non_status_changes:
        raise BusinessRuleError(
            "Change course-offering status in a separate request from its inputs."
        )
    if non_status_changes and offering.status != CourseOfferingStatus.DRAFT:
        raise ResourceInUseError(
            "Only a DRAFT course offering can change scheduling inputs.",
            details={"course_offering_id": offering.id},
        )
    sessions = _active_sessions(db, offering.id)
    structure_changed = (
        curriculum_course_id != offering.curriculum_course_id
        or academic_term_id != offering.academic_term_id
    )
    if sessions and structure_changed:
        raise ResourceInUseError(
            "An offering with sessions cannot change curriculum course or term.",
            details={
                "course_offering_id": offering.id,
                "course_session_id": sessions[0].id,
            },
        )

    _validate_curriculum_and_term(
        db,
        curriculum_course_id=curriculum_course_id,
        academic_term_id=academic_term_id,
        require_active_parents=new_status
        in {CourseOfferingStatus.DRAFT, CourseOfferingStatus.READY},
    )
    ensure_unique(
        db,
        CourseOffering,
        "Course offering",
        ["curriculum_course_id", "academic_term_id"],
        CourseOffering.curriculum_course_id == curriculum_course_id,
        CourseOffering.academic_term_id == academic_term_id,
        exclude_id=offering.id,
    )
    _validate_status_transition(db, offering, new_status)

    apply_changes(offering, changes)
    return commit_and_refresh(db, offering)


def delete_course_offering(
    db: Session,
    course_offering_id: int,
) -> MessageResponse:
    offering = get_course_offering(db, course_offering_id)
    _validate_status_transition(db, offering, CourseOfferingStatus.CANCELLED)
    offering.status = CourseOfferingStatus.CANCELLED
    commit_and_refresh(db, offering)
    return MessageResponse(message="Course offering cancelled successfully.")
