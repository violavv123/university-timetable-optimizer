from app.core.exceptions import (
    BusinessRuleError,
    DuplicateResourceError,
    InvalidReferenceError,
    ResourceNotFoundError,
)
from app.models.course_session import CourseSession
from app.models.course_session_group import CourseSessionGroup
from app.models.enums import ComponentType, RoomStatus, StudentGroupType
from app.models.room import Room
from app.models.student_group import StudentGroup
from app.schemas.common import MessageResponse, PaginatedResponse, PaginationParams
from app.schemas.course_session_group import (
    CourseSessionGroupCreate,
    CourseSessionGroupRead,
)
from app.services.academic.hierarchy import (
    require_active_program_semester_hierarchy,
)
from app.services.common import (
    commit_and_refresh,
    commit_delete,
    paginated_rows,
    require_active,
    require_by_id,
)
from app.services.scheduling_input.guards import require_editable_session
from sqlalchemy import func, select
from sqlalchemy.orm import Session

ALLOWED_GROUP_TYPES: dict[ComponentType, set[StudentGroupType]] = {
    ComponentType.LECTURE: {
        StudentGroupType.COHORT,
        StudentGroupType.LECTURE_GROUP,
    },
    ComponentType.NUMERICAL: {
        StudentGroupType.COHORT,
        StudentGroupType.NUMERICAL_GROUP,
    },
    ComponentType.LABORATORY: {
        StudentGroupType.COHORT,
        StudentGroupType.LAB_GROUP,
    },
}


def _ancestor_ids(db: Session, group: StudentGroup) -> set[int]:
    ancestors: set[int] = set()
    parent_id = group.parent_group_id
    while parent_id is not None:
        if parent_id in ancestors:
            raise BusinessRuleError(
                "The existing student-group hierarchy contains a cycle.",
                details={"student_group_id": group.id},
            )
        ancestors.add(parent_id)
        parent = require_by_id(
            db,
            StudentGroup,
            parent_id,
            "Parent student group",
        )
        parent_id = parent.parent_group_id
    return ancestors


def _validate_assignment(
    db: Session,
    *,
    session: CourseSession,
    group: StudentGroup,
) -> None:
    require_active(group, "Student group")
    require_active_program_semester_hierarchy(group.program_semester)
    require_active(group.academic_term, "Academic term")
    offering = session.course_offering
    curriculum_course = offering.curriculum_course
    if group.program_semester_id != curriculum_course.program_semester_id:
        raise InvalidReferenceError(
            "The group and course offering must belong to the same program semester.",
            details={
                "student_group_id": group.id,
                "group_program_semester_id": group.program_semester_id,
                "offering_program_semester_id": (curriculum_course.program_semester_id),
            },
        )
    if group.academic_term_id != offering.academic_term_id:
        raise InvalidReferenceError(
            "The group and course offering must belong to the same academic term.",
            details={
                "student_group_id": group.id,
                "group_academic_term_id": group.academic_term_id,
                "offering_academic_term_id": offering.academic_term_id,
            },
        )
    if group.group_type not in ALLOWED_GROUP_TYPES[session.component_type]:
        raise BusinessRuleError(
            "Student-group type is incompatible with the session component.",
            details={
                "course_session_id": session.id,
                "component_type": session.component_type,
                "student_group_id": group.id,
                "group_type": group.group_type,
            },
        )

    new_ancestors = _ancestor_ids(db, group)
    existing_groups = list(
        db.scalars(
            select(StudentGroup)
            .join(
                CourseSessionGroup,
                CourseSessionGroup.student_group_id == StudentGroup.id,
            )
            .where(CourseSessionGroup.course_session_id == session.id)
        ).all()
    )
    assigned_students = group.student_count
    for existing_group in existing_groups:
        existing_ancestors = _ancestor_ids(db, existing_group)
        if existing_group.id in new_ancestors or group.id in existing_ancestors:
            raise BusinessRuleError(
                "A session cannot contain both an ancestor group and its descendant.",
                details={
                    "course_session_id": session.id,
                    "student_group_id": group.id,
                    "conflicting_student_group_id": existing_group.id,
                },
            )
        assigned_students += existing_group.student_count

    if session.max_students is not None and assigned_students > session.max_students:
        raise BusinessRuleError(
            "Assigned student groups exceed session.max_students.",
            details={
                "course_session_id": session.id,
                "assigned_students": assigned_students,
                "max_students": session.max_students,
            },
        )
    if session.required_room_id is not None:
        room = require_by_id(db, Room, session.required_room_id, "Required room")
        if room.status != RoomStatus.ACTIVE:
            raise BusinessRuleError(
                "The specifically required room must be active.",
                details={"room_id": room.id},
            )
        if assigned_students > room.capacity:
            raise BusinessRuleError(
                "Assigned student groups exceed the required room's capacity.",
                details={
                    "course_session_id": session.id,
                    "room_id": room.id,
                    "assigned_students": assigned_students,
                    "room_capacity": room.capacity,
                },
            )


def get_course_session_group(
    db: Session,
    course_session_id: int,
    student_group_id: int,
) -> CourseSessionGroup:
    assignment = db.get(
        CourseSessionGroup,
        (course_session_id, student_group_id),
    )
    if assignment is None:
        raise ResourceNotFoundError(
            "Course-session group assignment",
            f"{course_session_id}:{student_group_id}",
        )
    return assignment


def list_course_session_groups(
    db: Session,
    pagination: PaginationParams,
    *,
    course_session_id: int | None = None,
    student_group_id: int | None = None,
) -> PaginatedResponse[CourseSessionGroupRead]:
    filters = []
    if course_session_id is not None:
        require_by_id(db, CourseSession, course_session_id, "Course session")
        filters.append(CourseSessionGroup.course_session_id == course_session_id)
    if student_group_id is not None:
        require_by_id(db, StudentGroup, student_group_id, "Student group")
        filters.append(CourseSessionGroup.student_group_id == student_group_id)

    statement = (
        select(CourseSessionGroup)
        .where(*filters)
        .order_by(
            CourseSessionGroup.course_session_id,
            CourseSessionGroup.student_group_id,
        )
    )
    count_statement = select(func.count()).select_from(CourseSessionGroup).where(*filters)
    rows, total = paginated_rows(db, statement, count_statement, pagination)
    return PaginatedResponse[CourseSessionGroupRead](
        items=[CourseSessionGroupRead.model_validate(row) for row in rows],
        total=total,
        page=pagination.page,
        page_size=pagination.page_size,
    )


def create_course_session_group(
    db: Session,
    payload: CourseSessionGroupCreate,
) -> CourseSessionGroup:
    session = require_editable_session(db, payload.course_session_id)
    group = require_by_id(
        db,
        StudentGroup,
        payload.student_group_id,
        "Student group",
    )
    if (
        db.get(
            CourseSessionGroup,
            (payload.course_session_id, payload.student_group_id),
        )
        is not None
    ):
        raise DuplicateResourceError(
            "Course-session group assignment",
            fields=["course_session_id", "student_group_id"],
        )
    _validate_assignment(db, session=session, group=group)

    assignment = CourseSessionGroup(**payload.model_dump())
    db.add(assignment)
    return commit_and_refresh(db, assignment)


def delete_course_session_group(
    db: Session,
    course_session_id: int,
    student_group_id: int,
) -> MessageResponse:
    require_editable_session(db, course_session_id)
    assignment = get_course_session_group(
        db,
        course_session_id,
        student_group_id,
    )
    commit_delete(db, assignment)
    return MessageResponse(message="Student group detached from session.")
