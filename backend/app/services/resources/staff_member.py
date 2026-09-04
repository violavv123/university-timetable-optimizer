from app.core.exceptions import BusinessRuleError, ResourceInUseError
from app.models.course_offering import CourseOffering
from app.models.course_session import CourseSession
from app.models.course_session_staff import CourseSessionStaff
from app.models.enums import CourseOfferingStatus
from app.models.faculty import Faculty
from app.models.staff_course import StaffCourse
from app.models.staff_member import StaffMember
from app.schemas.common import MessageResponse, PaginatedResponse, PaginationParams
from app.schemas.staff_member import (
    StaffMemberCreate,
    StaffMemberRead,
    StaffMemberUpdate,
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


def _normalize_name(value: str, field_name: str) -> str:
    normalized = " ".join(value.split())
    if not normalized:
        raise BusinessRuleError(f"{field_name} cannot be blank.")
    return normalized


def _normalize_email(value: str | None) -> str | None:
    if value is None:
        return None
    normalized = value.strip().lower()
    if not normalized:
        raise BusinessRuleError("email cannot be blank; use null when unknown.")
    return normalized


def _validate_faculty(
    db: Session,
    faculty_id: int,
    *,
    require_active_faculty: bool,
) -> None:
    faculty = require_by_id(db, Faculty, faculty_id, "Faculty")
    if require_active_faculty:
        require_active(faculty, "Faculty")


def _ensure_can_be_deactivated(db: Session, staff_member_id: int) -> None:
    active_qualification_id = db.scalar(
        select(StaffCourse.id)
        .where(
            StaffCourse.staff_member_id == staff_member_id,
            StaffCourse.is_active.is_(True),
        )
        .limit(1)
    )
    if active_qualification_id is not None:
        raise ResourceInUseError(
            "Staff member cannot be deactivated while teaching "
            "qualifications are active.",
            details={
                "staff_member_id": staff_member_id,
                "staff_course_id": active_qualification_id,
            },
        )

    active_assignment_id = db.scalar(
        select(CourseSession.id)
        .join(
            CourseSessionStaff,
            CourseSessionStaff.course_session_id == CourseSession.id,
        )
        .join(
            CourseOffering,
            CourseOffering.id == CourseSession.course_offering_id,
        )
        .where(
            CourseSessionStaff.staff_member_id == staff_member_id,
            CourseSession.is_active.is_(True),
            CourseOffering.status.in_(
                [CourseOfferingStatus.DRAFT, CourseOfferingStatus.READY]
            ),
        )
        .limit(1)
    )
    if active_assignment_id is not None:
        raise ResourceInUseError(
            "Staff member cannot be deactivated while assigned to an open "
            "course session.",
            details={
                "staff_member_id": staff_member_id,
                "course_session_id": active_assignment_id,
            },
        )


def get_staff_member(db: Session, staff_member_id: int) -> StaffMember:
    return require_by_id(db, StaffMember, staff_member_id, "Staff member")


def list_staff_members(
    db: Session,
    pagination: PaginationParams,
    *,
    faculty_id: int | None = None,
    include_inactive: bool = False,
) -> PaginatedResponse[StaffMemberRead]:
    filters = []
    if faculty_id is not None:
        require_by_id(db, Faculty, faculty_id, "Faculty")
        filters.append(StaffMember.faculty_id == faculty_id)
    if not include_inactive:
        filters.append(StaffMember.is_active.is_(True))

    statement = (
        select(StaffMember)
        .where(*filters)
        .order_by(StaffMember.last_name, StaffMember.first_name, StaffMember.id)
    )
    count_statement = select(func.count()).select_from(StaffMember).where(*filters)
    rows, total = paginated_rows(db, statement, count_statement, pagination)
    return PaginatedResponse[StaffMemberRead](
        items=[StaffMemberRead.model_validate(row) for row in rows],
        total=total,
        page=pagination.page,
        page_size=pagination.page_size,
    )


def create_staff_member(
    db: Session,
    payload: StaffMemberCreate,
) -> StaffMember:
    _validate_faculty(
        db,
        payload.faculty_id,
        require_active_faculty=payload.is_active,
    )
    values = payload.model_dump()
    values["first_name"] = _normalize_name(payload.first_name, "first_name")
    values["last_name"] = _normalize_name(payload.last_name, "last_name")
    values["email"] = _normalize_email(payload.email)
    if values["email"] is not None:
        ensure_unique(
            db,
            StaffMember,
            "Staff member",
            ["email"],
            func.lower(StaffMember.email) == values["email"],
        )

    staff_member = StaffMember(**values)
    db.add(staff_member)
    return commit_and_refresh(db, staff_member)


def update_staff_member(
    db: Session,
    staff_member_id: int,
    payload: StaffMemberUpdate,
) -> StaffMember:
    staff_member = get_staff_member(db, staff_member_id)
    changes = validated_changes(
        payload,
        non_nullable_fields=(
            "faculty_id",
            "first_name",
            "last_name",
            "staff_type",
            "is_active",
        ),
    )
    faculty_id = changes.get("faculty_id", staff_member.faculty_id)
    final_is_active = changes.get("is_active", staff_member.is_active)
    _validate_faculty(
        db,
        faculty_id,
        require_active_faculty=final_is_active,
    )

    if "first_name" in changes:
        changes["first_name"] = _normalize_name(changes["first_name"], "first_name")
    if "last_name" in changes:
        changes["last_name"] = _normalize_name(changes["last_name"], "last_name")
    if "email" in changes:
        changes["email"] = _normalize_email(changes["email"])
        if changes["email"] is not None:
            ensure_unique(
                db,
                StaffMember,
                "Staff member",
                ["email"],
                func.lower(StaffMember.email) == changes["email"],
                exclude_id=staff_member.id,
            )

    if changes.get("is_active") is False and staff_member.is_active:
        _ensure_can_be_deactivated(db, staff_member.id)

    apply_changes(staff_member, changes)
    return commit_and_refresh(db, staff_member)


def delete_staff_member(
    db: Session,
    staff_member_id: int,
) -> MessageResponse:
    staff_member = get_staff_member(db, staff_member_id)
    _ensure_can_be_deactivated(db, staff_member.id)
    staff_member.is_active = False
    commit_and_refresh(db, staff_member)
    return MessageResponse(message="Staff member deactivated successfully.")
