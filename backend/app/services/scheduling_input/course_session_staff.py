from app.core.exceptions import (
    BusinessRuleError,
    DuplicateResourceError,
    ResourceNotFoundError,
)
from app.models.course_session import CourseSession
from app.models.course_session_staff import CourseSessionStaff
from app.models.enums import ComponentType, TeachingRole
from app.models.staff_course import StaffCourse
from app.models.staff_member import StaffMember
from app.schemas.common import MessageResponse, PaginatedResponse, PaginationParams
from app.schemas.course_session_staff import (
    CourseSessionStaffCreate,
    CourseSessionStaffRead,
    CourseSessionStaffUpdate,
)
from app.services.common import (
    apply_changes,
    commit_and_refresh,
    commit_delete,
    paginated_rows,
    require_active,
    require_by_id,
    validated_changes,
)
from app.services.scheduling_input.guards import require_editable_session
from sqlalchemy import func, select
from sqlalchemy.orm import Session

EXPECTED_ROLE: dict[ComponentType, TeachingRole] = {
    ComponentType.LECTURE: TeachingRole.LECTURER,
    ComponentType.NUMERICAL: TeachingRole.NUMERICAL_INSTRUCTOR,
    ComponentType.LABORATORY: TeachingRole.LAB_INSTRUCTOR,
}


def _validate_assignment(
    db: Session,
    *,
    session: CourseSession,
    staff_member: StaffMember,
    teaching_role: TeachingRole,
    is_primary: bool,
    exclude_staff_member_id: int | None = None,
) -> None:
    require_active(staff_member, "Staff member")
    expected_role = EXPECTED_ROLE[session.component_type]
    if teaching_role != expected_role:
        raise BusinessRuleError(
            "teaching_role is incompatible with the session component.",
            details={
                "course_session_id": session.id,
                "component_type": session.component_type,
                "expected_teaching_role": expected_role,
                "teaching_role": teaching_role,
            },
        )

    course_id = session.course_offering.curriculum_course.course_id
    qualification = db.scalar(
        select(StaffCourse)
        .where(
            StaffCourse.staff_member_id == staff_member.id,
            StaffCourse.course_id == course_id,
            StaffCourse.is_active.is_(True),
        )
        .limit(1)
    )
    if qualification is None:
        raise BusinessRuleError(
            "The staff member has no active qualification for this course.",
            details={
                "staff_member_id": staff_member.id,
                "course_id": course_id,
            },
        )
    if teaching_role == TeachingRole.LECTURER and not qualification.can_lecture:
        raise BusinessRuleError(
            "A lecturer assignment requires can_lecture=True.",
            details={"staff_course_id": qualification.id},
        )
    if (
        teaching_role
        in {
            TeachingRole.NUMERICAL_INSTRUCTOR,
            TeachingRole.LAB_INSTRUCTOR,
        }
        and not qualification.can_assist
    ):
        raise BusinessRuleError(
            "A numerical or laboratory assignment requires can_assist=True.",
            details={"staff_course_id": qualification.id},
        )

    if is_primary:
        statement = select(CourseSessionStaff.staff_member_id).where(
            CourseSessionStaff.course_session_id == session.id,
            CourseSessionStaff.is_primary.is_(True),
        )
        if exclude_staff_member_id is not None:
            statement = statement.where(
                CourseSessionStaff.staff_member_id != exclude_staff_member_id
            )
        existing_primary_id = db.scalar(statement.limit(1))
        if existing_primary_id is not None:
            raise BusinessRuleError(
                "A course session can have only one primary staff member.",
                details={
                    "course_session_id": session.id,
                    "primary_staff_member_id": existing_primary_id,
                },
            )


def get_course_session_staff(
    db: Session,
    course_session_id: int,
    staff_member_id: int,
) -> CourseSessionStaff:
    assignment = db.get(
        CourseSessionStaff,
        (course_session_id, staff_member_id),
    )
    if assignment is None:
        raise ResourceNotFoundError(
            "Course-session staff assignment",
            f"{course_session_id}:{staff_member_id}",
        )
    return assignment


def list_course_session_staff(
    db: Session,
    pagination: PaginationParams,
    *,
    course_session_id: int | None = None,
    staff_member_id: int | None = None,
) -> PaginatedResponse[CourseSessionStaffRead]:
    filters = []
    if course_session_id is not None:
        require_by_id(db, CourseSession, course_session_id, "Course session")
        filters.append(CourseSessionStaff.course_session_id == course_session_id)
    if staff_member_id is not None:
        require_by_id(db, StaffMember, staff_member_id, "Staff member")
        filters.append(CourseSessionStaff.staff_member_id == staff_member_id)

    statement = (
        select(CourseSessionStaff)
        .where(*filters)
        .order_by(
            CourseSessionStaff.course_session_id,
            CourseSessionStaff.is_primary.desc(),
            CourseSessionStaff.staff_member_id,
        )
    )
    count_statement = select(func.count()).select_from(CourseSessionStaff).where(*filters)
    rows, total = paginated_rows(db, statement, count_statement, pagination)
    return PaginatedResponse[CourseSessionStaffRead](
        items=[CourseSessionStaffRead.model_validate(row) for row in rows],
        total=total,
        page=pagination.page,
        page_size=pagination.page_size,
    )


def create_course_session_staff(
    db: Session,
    payload: CourseSessionStaffCreate,
) -> CourseSessionStaff:
    session = require_editable_session(db, payload.course_session_id)
    staff_member = require_by_id(
        db,
        StaffMember,
        payload.staff_member_id,
        "Staff member",
    )
    if (
        db.get(
            CourseSessionStaff,
            (payload.course_session_id, payload.staff_member_id),
        )
        is not None
    ):
        raise DuplicateResourceError(
            "Course-session staff assignment",
            fields=["course_session_id", "staff_member_id"],
        )
    _validate_assignment(
        db,
        session=session,
        staff_member=staff_member,
        teaching_role=payload.teaching_role,
        is_primary=payload.is_primary,
    )

    assignment = CourseSessionStaff(**payload.model_dump())
    db.add(assignment)
    return commit_and_refresh(db, assignment)


def update_course_session_staff(
    db: Session,
    course_session_id: int,
    staff_member_id: int,
    payload: CourseSessionStaffUpdate,
) -> CourseSessionStaff:
    session = require_editable_session(db, course_session_id)
    assignment = get_course_session_staff(
        db,
        course_session_id,
        staff_member_id,
    )
    changes = validated_changes(
        payload,
        non_nullable_fields=("teaching_role", "is_primary", "is_fixed"),
    )
    if {"course_session_id", "staff_member_id"}.intersection(changes):
        raise BusinessRuleError(
            "Course-session staff identifiers are immutable; detach and "
            "create a new assignment instead."
        )
    teaching_role = changes.get("teaching_role", assignment.teaching_role)
    is_primary = changes.get("is_primary", assignment.is_primary)
    staff_member = require_by_id(
        db,
        StaffMember,
        staff_member_id,
        "Staff member",
    )
    _validate_assignment(
        db,
        session=session,
        staff_member=staff_member,
        teaching_role=teaching_role,
        is_primary=is_primary,
        exclude_staff_member_id=staff_member_id,
    )

    apply_changes(assignment, changes)
    return commit_and_refresh(db, assignment)


def delete_course_session_staff(
    db: Session,
    course_session_id: int,
    staff_member_id: int,
) -> MessageResponse:
    require_editable_session(db, course_session_id)
    assignment = get_course_session_staff(
        db,
        course_session_id,
        staff_member_id,
    )
    commit_delete(db, assignment)
    return MessageResponse(message="Staff member detached from session.")
