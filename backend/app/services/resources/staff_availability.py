from app.models.academic_term import AcademicTerm
from app.models.staff_availability import StaffAvailability
from app.models.staff_member import StaffMember
from app.schemas.common import MessageResponse, PaginatedResponse, PaginationParams
from app.schemas.staff_availability import (
    StaffAvailabilityCreate,
    StaffAvailabilityRead,
    StaffAvailabilityUpdate,
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
from app.services.resources.availability_validation import (
    ensure_no_overlapping_window,
    validate_availability_values,
)
from sqlalchemy import func, select
from sqlalchemy.orm import Session


def _validate_parents(
    db: Session,
    *,
    staff_member_id: int,
    academic_term_id: int,
) -> None:
    staff_member = require_by_id(db, StaffMember, staff_member_id, "Staff member")
    academic_term = require_by_id(
        db,
        AcademicTerm,
        academic_term_id,
        "Academic term",
    )
    require_active(staff_member, "Staff member")
    require_active(academic_term, "Academic term")


def get_staff_availability(
    db: Session,
    staff_availability_id: int,
) -> StaffAvailability:
    return require_by_id(
        db,
        StaffAvailability,
        staff_availability_id,
        "Staff availability",
    )


def list_staff_availabilities(
    db: Session,
    pagination: PaginationParams,
    *,
    staff_member_id: int | None = None,
    academic_term_id: int | None = None,
) -> PaginatedResponse[StaffAvailabilityRead]:
    filters = []
    if staff_member_id is not None:
        require_by_id(db, StaffMember, staff_member_id, "Staff member")
        filters.append(StaffAvailability.staff_member_id == staff_member_id)
    if academic_term_id is not None:
        require_by_id(db, AcademicTerm, academic_term_id, "Academic term")
        filters.append(StaffAvailability.academic_term_id == academic_term_id)

    statement = (
        select(StaffAvailability)
        .where(*filters)
        .order_by(
            StaffAvailability.staff_member_id,
            StaffAvailability.academic_term_id,
            StaffAvailability.day_of_week,
            StaffAvailability.start_time,
        )
    )
    count_statement = (
        select(func.count()).select_from(StaffAvailability).where(*filters)
    )
    rows, total = paginated_rows(db, statement, count_statement, pagination)
    return PaginatedResponse[StaffAvailabilityRead](
        items=[StaffAvailabilityRead.model_validate(row) for row in rows],
        total=total,
        page=pagination.page,
        page_size=pagination.page_size,
    )


def create_staff_availability(
    db: Session,
    payload: StaffAvailabilityCreate,
) -> StaffAvailability:
    _validate_parents(
        db,
        staff_member_id=payload.staff_member_id,
        academic_term_id=payload.academic_term_id,
    )
    validate_availability_values(
        day_of_week=payload.day_of_week,
        start_time=payload.start_time,
        end_time=payload.end_time,
        availability_type=payload.availability_type,
        preference_weight=payload.preference_weight,
    )
    ensure_no_overlapping_window(
        db,
        StaffAvailability,
        owner_field="staff_member_id",
        owner_id=payload.staff_member_id,
        academic_term_id=payload.academic_term_id,
        day_of_week=payload.day_of_week,
        start_time=payload.start_time,
        end_time=payload.end_time,
        resource_name="Staff availability",
    )

    availability = StaffAvailability(**payload.model_dump())
    db.add(availability)
    return commit_and_refresh(db, availability)


def update_staff_availability(
    db: Session,
    staff_availability_id: int,
    payload: StaffAvailabilityUpdate,
) -> StaffAvailability:
    availability = get_staff_availability(db, staff_availability_id)
    changes = validated_changes(
        payload,
        non_nullable_fields=(
            "staff_member_id",
            "academic_term_id",
            "day_of_week",
            "start_time",
            "end_time",
            "availability_type",
        ),
    )
    staff_member_id = changes.get(
        "staff_member_id",
        availability.staff_member_id,
    )
    academic_term_id = changes.get(
        "academic_term_id",
        availability.academic_term_id,
    )
    day_of_week = changes.get("day_of_week", availability.day_of_week)
    start_time = changes.get("start_time", availability.start_time)
    end_time = changes.get("end_time", availability.end_time)
    availability_type = changes.get(
        "availability_type",
        availability.availability_type,
    )
    preference_weight = changes.get(
        "preference_weight",
        availability.preference_weight,
    )

    _validate_parents(
        db,
        staff_member_id=staff_member_id,
        academic_term_id=academic_term_id,
    )
    validate_availability_values(
        day_of_week=day_of_week,
        start_time=start_time,
        end_time=end_time,
        availability_type=availability_type,
        preference_weight=preference_weight,
    )
    ensure_no_overlapping_window(
        db,
        StaffAvailability,
        owner_field="staff_member_id",
        owner_id=staff_member_id,
        academic_term_id=academic_term_id,
        day_of_week=day_of_week,
        start_time=start_time,
        end_time=end_time,
        resource_name="Staff availability",
        exclude_id=availability.id,
    )

    apply_changes(availability, changes)
    return commit_and_refresh(db, availability)


def delete_staff_availability(
    db: Session,
    staff_availability_id: int,
) -> MessageResponse:
    availability = get_staff_availability(db, staff_availability_id)
    commit_delete(db, availability)
    return MessageResponse(message="Staff availability deleted successfully.")
