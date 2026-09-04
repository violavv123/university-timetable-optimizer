from datetime import time

from app.core.exceptions import (
    BusinessRuleError,
    InvalidReferenceError,
    ResourceInUseError,
)
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
    RoomStatus,
    RoomType,
    TimeConstraintType,
)
from app.models.room import Room
from app.models.student_group import StudentGroup
from app.models.timetable_entry import TimetableEntry
from app.schemas.common import MessageResponse, PaginatedResponse, PaginationParams
from app.schemas.course_session import (
    CourseSessionCreate,
    CourseSessionRead,
    CourseSessionUpdate,
)
from app.services.common import (
    apply_changes,
    commit_and_refresh,
    ensure_unique,
    flush_transaction,
    paginated_rows,
    require_active,
    require_by_id,
    validated_changes,
)
from sqlalchemy import func, select
from sqlalchemy.orm import Session

MASTER_LEVEL_CODE = "MSC"
MASTER_EARLIEST_TIME = time(8, 0)
MASTER_PREFERRED_START = time(17, 0)
MASTER_LATEST_END = time(20, 0)


def _curriculum_periods(
    curriculum_course: CurriculumCourse,
    component_type: ComponentType,
) -> int:
    if component_type == ComponentType.LECTURE:
        return curriculum_course.lecture_periods_per_week
    if component_type == ComponentType.NUMERICAL:
        return curriculum_course.numerical_periods_per_week
    return curriculum_course.laboratory_periods_per_week


def _require_draft_offering(
    db: Session,
    course_offering_id: int,
) -> CourseOffering:
    offering = require_by_id(
        db,
        CourseOffering,
        course_offering_id,
        "Course offering",
    )
    if offering.status != CourseOfferingStatus.DRAFT:
        raise ResourceInUseError(
            "Course sessions can only be changed while the offering is DRAFT.",
            details={
                "course_offering_id": offering.id,
                "course_offering_status": offering.status,
            },
        )
    require_active(offering.curriculum_course, "Curriculum course")
    require_active(offering.academic_term, "Academic term")
    return offering


def _assigned_student_count(db: Session, course_session_id: int) -> int:
    return int(
        db.scalar(
            select(func.coalesce(func.sum(StudentGroup.student_count), 0))
            .select_from(CourseSessionGroup)
            .join(
                StudentGroup,
                StudentGroup.id == CourseSessionGroup.student_group_id,
            )
            .where(
                CourseSessionGroup.course_session_id == course_session_id,
                StudentGroup.is_active.is_(True),
            )
        )
        or 0
    )


def _validate_required_room(
    db: Session,
    *,
    offering: CourseOffering,
    course_session_id: int | None,
    component_type: ComponentType,
    max_students: int | None,
    required_room_type: RoomType | None,
    required_room_id: int | None,
) -> None:
    if component_type == ComponentType.LABORATORY:
        if required_room_id is None and required_room_type != RoomType.LABORATORY:
            raise BusinessRuleError("A laboratory session must require a laboratory room.")
    if required_room_id is None:
        return

    room = require_by_id(db, Room, required_room_id, "Required room")
    if room.status != RoomStatus.ACTIVE:
        raise BusinessRuleError(
            "A specifically required room must be active.",
            details={"room_id": room.id, "room_status": room.status},
        )
    if required_room_type is not None and room.room_type != required_room_type:
        raise InvalidReferenceError(
            "The required room does not match required_room_type.",
            details={
                "room_id": room.id,
                "room_type": room.room_type,
                "required_room_type": required_room_type,
            },
        )
    if component_type == ComponentType.LABORATORY and room.room_type != RoomType.LABORATORY:
        raise InvalidReferenceError(
            "A laboratory session's required room must be a laboratory.",
            details={"room_id": room.id},
        )

    program = offering.curriculum_course.program_semester.study_program
    if room.faculty_id != program.faculty_id:
        raise InvalidReferenceError(
            "A specifically required room must belong to the offering's faculty.",
            details={
                "room_id": room.id,
                "room_faculty_id": room.faculty_id,
                "study_program_id": program.id,
                "study_program_faculty_id": program.faculty_id,
            },
        )

    assigned_students = (
        0 if course_session_id is None else _assigned_student_count(db, course_session_id)
    )
    required_capacity = assigned_students
    if required_capacity == 0:
        required_capacity = max_students or offering.expected_students or 0
    if required_capacity > room.capacity:
        raise BusinessRuleError(
            "The specifically required room is too small for this session.",
            details={
                "room_id": room.id,
                "room_capacity": room.capacity,
                "required_capacity": required_capacity,
            },
        )


def _validate_component_periods(
    db: Session,
    *,
    offering: CourseOffering,
    component_type: ComponentType,
    weekly_frequency: int,
    duration_slots: int,
    final_is_active: bool,
    exclude_id: int | None = None,
) -> None:
    allowed_periods = _curriculum_periods(
        offering.curriculum_course,
        component_type,
    )
    if allowed_periods <= 0:
        raise BusinessRuleError(
            "The curriculum course has no weekly periods for this component.",
            details={
                "curriculum_course_id": offering.curriculum_course_id,
                "component_type": component_type,
            },
        )

    statement = select(
        func.coalesce(
            func.sum(CourseSession.weekly_frequency * CourseSession.duration_slots),
            0,
        )
    ).where(
        CourseSession.course_offering_id == offering.id,
        CourseSession.component_type == component_type,
        CourseSession.is_active.is_(True),
    )
    if exclude_id is not None:
        statement = statement.where(CourseSession.id != exclude_id)
    existing_periods = int(db.scalar(statement) or 0)
    requested_periods = weekly_frequency * duration_slots if final_is_active else 0
    if existing_periods + requested_periods > allowed_periods:
        raise BusinessRuleError(
            "Active sessions exceed the curriculum's weekly component periods.",
            details={
                "course_offering_id": offering.id,
                "component_type": component_type,
                "curriculum_periods": allowed_periods,
                "requested_total_periods": existing_periods + requested_periods,
            },
        )


def _validate_session_values(
    db: Session,
    *,
    offering: CourseOffering,
    course_session_id: int | None,
    component_type: ComponentType,
    weekly_frequency: int,
    duration_slots: int,
    max_students: int | None,
    is_splittable: bool,
    required_room_type: RoomType | None,
    required_room_id: int | None,
    final_is_active: bool,
) -> None:
    if weekly_frequency <= 0:
        raise BusinessRuleError("weekly_frequency must be greater than zero.")
    if duration_slots <= 0:
        raise BusinessRuleError("duration_slots must be greater than zero.")
    if max_students is not None and max_students <= 0:
        raise BusinessRuleError("max_students must be greater than zero.")
    if is_splittable and max_students is None:
        raise BusinessRuleError("A splittable session requires max_students to define split size.")
    assigned_students = (
        0 if course_session_id is None else _assigned_student_count(db, course_session_id)
    )
    if max_students is not None and assigned_students > max_students:
        raise BusinessRuleError(
            "max_students cannot be smaller than the assigned student groups.",
            details={
                "course_session_id": course_session_id,
                "assigned_students": assigned_students,
                "max_students": max_students,
            },
        )
    _validate_component_periods(
        db,
        offering=offering,
        component_type=component_type,
        weekly_frequency=weekly_frequency,
        duration_slots=duration_slots,
        final_is_active=final_is_active,
        exclude_id=course_session_id,
    )
    _validate_required_room(
        db,
        offering=offering,
        course_session_id=course_session_id,
        component_type=component_type,
        max_students=max_students,
        required_room_type=required_room_type,
        required_room_id=required_room_id,
    )


def _has_session_children(db: Session, course_session_id: int) -> bool:
    checks = (
        select(CourseSessionGroup.course_session_id).where(
            CourseSessionGroup.course_session_id == course_session_id
        ),
        select(CourseSessionStaff.course_session_id).where(
            CourseSessionStaff.course_session_id == course_session_id
        ),
        select(CourseSessionTimeConstraint.id).where(
            CourseSessionTimeConstraint.course_session_id == course_session_id
        ),
        select(CourseSessionDependency.id).where(
            (CourseSessionDependency.predecessor_session_id == course_session_id)
            | (CourseSessionDependency.successor_session_id == course_session_id)
        ),
    )
    return any(db.scalar(statement.limit(1)) is not None for statement in checks)


def _ensure_no_timetable_entries(db: Session, course_session_id: int) -> None:
    timetable_entry_id = db.scalar(
        select(TimetableEntry.id)
        .where(TimetableEntry.course_session_id == course_session_id)
        .limit(1)
    )
    if timetable_entry_id is not None:
        raise ResourceInUseError(
            "A course session with timetable entries cannot be changed or deactivated.",
            details={
                "course_session_id": course_session_id,
                "timetable_entry_id": timetable_entry_id,
            },
        )


def _add_master_time_policy(
    db: Session,
    session: CourseSession,
    offering: CourseOffering,
) -> None:
    level_code = offering.curriculum_course.program_semester.study_program.level.code
    if level_code.strip().upper() != MASTER_LEVEL_CODE or not session.is_active:
        return
    db.add_all(
        [
            CourseSessionTimeConstraint(
                course_session_id=session.id,
                day_of_week=None,
                start_time=MASTER_EARLIEST_TIME,
                end_time=MASTER_LATEST_END,
                constraint_type=TimeConstraintType.ALLOWED_WINDOW,
                preference_weight=None,
            ),
            CourseSessionTimeConstraint(
                course_session_id=session.id,
                day_of_week=None,
                start_time=MASTER_PREFERRED_START,
                end_time=MASTER_LATEST_END,
                constraint_type=TimeConstraintType.PREFERRED_WINDOW,
                preference_weight=1,
            ),
        ]
    )


def get_course_session(db: Session, course_session_id: int) -> CourseSession:
    return require_by_id(db, CourseSession, course_session_id, "Course session")


def list_course_sessions(
    db: Session,
    pagination: PaginationParams,
    *,
    course_offering_id: int | None = None,
    component_type: ComponentType | None = None,
    include_inactive: bool = False,
) -> PaginatedResponse[CourseSessionRead]:
    filters = []
    if course_offering_id is not None:
        require_by_id(
            db,
            CourseOffering,
            course_offering_id,
            "Course offering",
        )
        filters.append(CourseSession.course_offering_id == course_offering_id)
    if component_type is not None:
        filters.append(CourseSession.component_type == component_type)
    if not include_inactive:
        filters.append(CourseSession.is_active.is_(True))

    statement = (
        select(CourseSession)
        .where(*filters)
        .order_by(
            CourseSession.course_offering_id,
            CourseSession.component_type,
            CourseSession.name,
        )
    )
    count_statement = select(func.count()).select_from(CourseSession).where(*filters)
    rows, total = paginated_rows(db, statement, count_statement, pagination)
    return PaginatedResponse[CourseSessionRead](
        items=[CourseSessionRead.model_validate(row) for row in rows],
        total=total,
        page=pagination.page,
        page_size=pagination.page_size,
    )


def create_course_session(
    db: Session,
    payload: CourseSessionCreate,
) -> CourseSession:
    offering = _require_draft_offering(db, payload.course_offering_id)
    values = payload.model_dump()
    values["name"] = " ".join(payload.name.split())
    if not values["name"]:
        raise BusinessRuleError("name cannot be blank.")
    if (
        payload.component_type == ComponentType.LABORATORY
        and payload.required_room_id is None
        and payload.required_room_type is None
    ):
        values["required_room_type"] = RoomType.LABORATORY

    _validate_session_values(
        db,
        offering=offering,
        course_session_id=None,
        component_type=payload.component_type,
        weekly_frequency=payload.weekly_frequency,
        duration_slots=payload.duration_slots,
        max_students=payload.max_students,
        is_splittable=payload.is_splittable,
        required_room_type=values["required_room_type"],
        required_room_id=payload.required_room_id,
        final_is_active=payload.is_active,
    )
    ensure_unique(
        db,
        CourseSession,
        "Course session",
        ["course_offering_id", "name"],
        CourseSession.course_offering_id == payload.course_offering_id,
        func.lower(CourseSession.name) == values["name"].lower(),
    )

    session = CourseSession(**values)
    db.add(session)
    flush_transaction(db)
    _add_master_time_policy(db, session, offering)
    return commit_and_refresh(db, session)


def update_course_session(
    db: Session,
    course_session_id: int,
    payload: CourseSessionUpdate,
) -> CourseSession:
    session = get_course_session(db, course_session_id)
    _ensure_no_timetable_entries(db, session.id)
    changes = validated_changes(
        payload,
        non_nullable_fields=(
            "course_offering_id",
            "name",
            "component_type",
            "weekly_frequency",
            "duration_slots",
            "is_splittable",
            "is_active",
        ),
    )
    original_offering = _require_draft_offering(db, session.course_offering_id)
    course_offering_id = changes.get(
        "course_offering_id",
        session.course_offering_id,
    )
    offering = (
        original_offering
        if course_offering_id == original_offering.id
        else _require_draft_offering(db, course_offering_id)
    )
    component_type = changes.get("component_type", session.component_type)
    weekly_frequency = changes.get(
        "weekly_frequency",
        session.weekly_frequency,
    )
    duration_slots = changes.get("duration_slots", session.duration_slots)
    max_students = changes.get("max_students", session.max_students)
    required_room_type = changes.get(
        "required_room_type",
        session.required_room_type,
    )
    required_room_id = changes.get("required_room_id", session.required_room_id)
    is_splittable = changes.get("is_splittable", session.is_splittable)
    final_is_active = changes.get("is_active", session.is_active)
    if "name" in changes:
        changes["name"] = " ".join(changes["name"].split())
        if not changes["name"]:
            raise BusinessRuleError("name cannot be blank.")
    name = changes.get("name", session.name)

    if component_type == ComponentType.LABORATORY:
        if required_room_id is None and required_room_type is None:
            required_room_type = RoomType.LABORATORY
            changes["required_room_type"] = RoomType.LABORATORY
    structure_changed = (
        course_offering_id != session.course_offering_id or component_type != session.component_type
    )
    if structure_changed and _has_session_children(db, session.id):
        raise ResourceInUseError(
            "A session with assignments or constraints cannot change offering or component.",
            details={"course_session_id": session.id},
        )
    if not final_is_active and _has_session_children(db, session.id):
        raise ResourceInUseError(
            "Remove session assignments, constraints, and dependencies before deactivation.",
            details={"course_session_id": session.id},
        )

    _validate_session_values(
        db,
        offering=offering,
        course_session_id=session.id,
        component_type=component_type,
        weekly_frequency=weekly_frequency,
        duration_slots=duration_slots,
        max_students=max_students,
        is_splittable=is_splittable,
        required_room_type=required_room_type,
        required_room_id=required_room_id,
        final_is_active=final_is_active,
    )
    ensure_unique(
        db,
        CourseSession,
        "Course session",
        ["course_offering_id", "name"],
        CourseSession.course_offering_id == course_offering_id,
        func.lower(CourseSession.name) == name.lower(),
        exclude_id=session.id,
    )

    apply_changes(session, changes)
    return commit_and_refresh(db, session)


def delete_course_session(
    db: Session,
    course_session_id: int,
) -> MessageResponse:
    session = get_course_session(db, course_session_id)
    _require_draft_offering(db, session.course_offering_id)
    _ensure_no_timetable_entries(db, session.id)
    if _has_session_children(db, session.id):
        raise ResourceInUseError(
            "Remove session assignments, constraints, and dependencies before deactivation.",
            details={"course_session_id": session.id},
        )
    session.is_active = False
    commit_and_refresh(db, session)
    return MessageResponse(message="Course session deactivated successfully.")
