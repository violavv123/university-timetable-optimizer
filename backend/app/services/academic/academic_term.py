from datetime import date

from app.core.exceptions import BusinessRuleError, ResourceInUseError
from app.models.academic_term import AcademicTerm
from app.models.academic_year import AcademicYear
from app.models.course_offering import CourseOffering
from app.models.enums import (
    CourseOfferingStatus,
    TermType,
    TimetableRunStatus,
)
from app.models.room_availability import RoomAvailability
from app.models.staff_availability import StaffAvailability
from app.models.student_group import StudentGroup
from app.models.timetable_run import TimetableRun
from app.schemas.academic_term import (
    AcademicTermCreate,
    AcademicTermRead,
    AcademicTermUpdate,
)
from app.schemas.common import MessageResponse, PaginatedResponse, PaginationParams
from app.services.academic._common import (
    apply_changes,
    commit_and_refresh,
    ensure_unique,
    paginated_rows,
    require_by_id,
    validated_changes,
)
from sqlalchemy import func, select
from sqlalchemy.orm import Session


def _validate_term_dates(
    academic_year: AcademicYear,
    start_date: date,
    end_date: date,
) -> None:
    if end_date <= start_date:
        raise BusinessRuleError("end_date must be after start_date.")
    if start_date < academic_year.start_date or end_date > academic_year.end_date:
        raise BusinessRuleError(
            "Academic-term dates must fit inside the academic year.",
            details={
                "academic_year_id": academic_year.id,
                "academic_year_start": academic_year.start_date,
                "academic_year_end": academic_year.end_date,
                "term_start": start_date,
                "term_end": end_date,
            },
        )


def _validate_term_order_and_overlap(
    db: Session,
    *,
    academic_year_id: int,
    term_type: TermType,
    start_date: date,
    end_date: date,
    exclude_id: int | None = None,
) -> None:
    statement = select(AcademicTerm).where(
        AcademicTerm.academic_year_id == academic_year_id,
    )
    if exclude_id is not None:
        statement = statement.where(AcademicTerm.id != exclude_id)

    for other_term in db.scalars(statement).all():
        overlaps = other_term.start_date <= end_date and other_term.end_date >= start_date
        if overlaps:
            raise BusinessRuleError(
                "Academic terms in the same year cannot overlap.",
                details={
                    "academic_term_id": exclude_id,
                    "overlapping_academic_term_id": other_term.id,
                },
            )

        winter_after_summer = (
            term_type == TermType.WINTER
            and other_term.term_type == TermType.SUMMER
            and start_date >= other_term.start_date
        )
        summer_before_winter = (
            term_type == TermType.SUMMER
            and other_term.term_type == TermType.WINTER
            and start_date <= other_term.start_date
        )
        if winter_after_summer or summer_before_winter:
            raise BusinessRuleError(
                "The winter term must occur before the summer term.",
                details={
                    "academic_term_id": exclude_id,
                    "other_academic_term_id": other_term.id,
                },
            )


def _ensure_term_structure_is_mutable(
    db: Session,
    academic_term_id: int,
) -> None:
    dependencies = (
        (
            "staff availability",
            StaffAvailability.id,
            StaffAvailability.academic_term_id == academic_term_id,
        ),
        (
            "room availability",
            RoomAvailability.id,
            RoomAvailability.academic_term_id == academic_term_id,
        ),
        (
            "student group",
            StudentGroup.id,
            StudentGroup.academic_term_id == academic_term_id,
        ),
        (
            "course offering",
            CourseOffering.id,
            CourseOffering.academic_term_id == academic_term_id,
        ),
        (
            "timetable run",
            TimetableRun.id,
            TimetableRun.academic_term_id == academic_term_id,
        ),
    )
    for resource_name, identifier, condition in dependencies:
        dependent_id = db.scalar(select(identifier).where(condition).limit(1))
        if dependent_id is not None:
            raise ResourceInUseError(
                "A referenced academic term cannot be structurally changed.",
                details={
                    "academic_term_id": academic_term_id,
                    "dependent_resource": resource_name,
                    "dependent_id": dependent_id,
                },
            )


def _ensure_term_can_be_deactivated(
    db: Session,
    academic_term_id: int,
) -> None:
    active_group_id = db.scalar(
        select(StudentGroup.id)
        .where(
            StudentGroup.academic_term_id == academic_term_id,
            StudentGroup.is_active.is_(True),
        )
        .limit(1)
    )
    if active_group_id is not None:
        raise ResourceInUseError(
            "Academic term cannot be deactivated while student groups are active.",
            details={
                "academic_term_id": academic_term_id,
                "student_group_id": active_group_id,
            },
        )

    open_offering_id = db.scalar(
        select(CourseOffering.id)
        .where(
            CourseOffering.academic_term_id == academic_term_id,
            CourseOffering.status.in_([CourseOfferingStatus.DRAFT, CourseOfferingStatus.READY]),
        )
        .limit(1)
    )
    if open_offering_id is not None:
        raise ResourceInUseError(
            "Academic term cannot be deactivated while offerings are open.",
            details={
                "academic_term_id": academic_term_id,
                "course_offering_id": open_offering_id,
            },
        )

    running_timetable_id = db.scalar(
        select(TimetableRun.id)
        .where(
            TimetableRun.academic_term_id == academic_term_id,
            TimetableRun.status.in_([TimetableRunStatus.PENDING, TimetableRunStatus.RUNNING]),
        )
        .limit(1)
    )
    if running_timetable_id is not None:
        raise ResourceInUseError(
            "Academic term cannot be deactivated while timetable work is running.",
            details={
                "academic_term_id": academic_term_id,
                "timetable_run_id": running_timetable_id,
            },
        )


def get_academic_term(db: Session, academic_term_id: int) -> AcademicTerm:
    return require_by_id(db, AcademicTerm, academic_term_id, "Academic term")


def list_academic_terms(
    db: Session,
    pagination: PaginationParams,
    *,
    academic_year_id: int | None = None,
    include_inactive: bool = False,
) -> PaginatedResponse[AcademicTermRead]:
    filters = []
    if academic_year_id is not None:
        require_by_id(db, AcademicYear, academic_year_id, "Academic year")
        filters.append(AcademicTerm.academic_year_id == academic_year_id)
    if not include_inactive:
        filters.append(AcademicTerm.is_active.is_(True))

    statement = (
        select(AcademicTerm)
        .where(*filters)
        .order_by(AcademicTerm.start_date.desc(), AcademicTerm.id.desc())
    )
    count_statement = select(func.count()).select_from(AcademicTerm).where(*filters)
    rows, total = paginated_rows(db, statement, count_statement, pagination)
    return PaginatedResponse[AcademicTermRead](
        items=[AcademicTermRead.model_validate(row) for row in rows],
        total=total,
        page=pagination.page,
        page_size=pagination.page_size,
    )


def create_academic_term(
    db: Session,
    payload: AcademicTermCreate,
) -> AcademicTerm:
    academic_year = require_by_id(
        db,
        AcademicYear,
        payload.academic_year_id,
        "Academic year",
    )
    _validate_term_dates(academic_year, payload.start_date, payload.end_date)
    _validate_term_order_and_overlap(
        db,
        academic_year_id=payload.academic_year_id,
        term_type=payload.term_type,
        start_date=payload.start_date,
        end_date=payload.end_date,
    )
    ensure_unique(
        db,
        AcademicTerm,
        "Academic term",
        ["academic_year_id", "term_type"],
        AcademicTerm.academic_year_id == payload.academic_year_id,
        AcademicTerm.term_type == payload.term_type,
    )

    academic_term = AcademicTerm(**payload.model_dump())
    db.add(academic_term)
    return commit_and_refresh(db, academic_term)


def update_academic_term(
    db: Session,
    academic_term_id: int,
    payload: AcademicTermUpdate,
) -> AcademicTerm:
    academic_term = get_academic_term(db, academic_term_id)
    changes = validated_changes(
        payload,
        non_nullable_fields=(
            "academic_year_id",
            "name",
            "term_type",
            "start_date",
            "end_date",
            "is_active",
        ),
    )
    academic_year_id = changes.get(
        "academic_year_id",
        academic_term.academic_year_id,
    )
    term_type: TermType = changes.get("term_type", academic_term.term_type)
    start_date = changes.get("start_date", academic_term.start_date)
    end_date = changes.get("end_date", academic_term.end_date)

    structural_fields = {
        "academic_year_id",
        "term_type",
        "start_date",
        "end_date",
    }
    if structural_fields.intersection(changes):
        _ensure_term_structure_is_mutable(db, academic_term.id)
    if changes.get("is_active") is False and academic_term.is_active:
        _ensure_term_can_be_deactivated(db, academic_term.id)

    academic_year = require_by_id(
        db,
        AcademicYear,
        academic_year_id,
        "Academic year",
    )
    _validate_term_dates(academic_year, start_date, end_date)
    _validate_term_order_and_overlap(
        db,
        academic_year_id=academic_year_id,
        term_type=term_type,
        start_date=start_date,
        end_date=end_date,
        exclude_id=academic_term.id,
    )
    ensure_unique(
        db,
        AcademicTerm,
        "Academic term",
        ["academic_year_id", "term_type"],
        AcademicTerm.academic_year_id == academic_year_id,
        AcademicTerm.term_type == term_type,
        exclude_id=academic_term.id,
    )

    apply_changes(academic_term, changes)
    return commit_and_refresh(db, academic_term)


def delete_academic_term(
    db: Session,
    academic_term_id: int,
) -> MessageResponse:
    academic_term = get_academic_term(db, academic_term_id)
    _ensure_term_can_be_deactivated(db, academic_term.id)
    academic_term.is_active = False
    commit_and_refresh(db, academic_term)
    return MessageResponse(message="Academic term deactivated successfully.")
