from app.core.exceptions import BusinessRuleError
from app.models.academic_term import AcademicTerm
from app.models.enums import RoomStatus
from app.models.room import Room
from app.models.room_availability import RoomAvailability
from app.schemas.common import MessageResponse, PaginatedResponse, PaginationParams
from app.schemas.room_availability import (
    RoomAvailabilityCreate,
    RoomAvailabilityRead,
    RoomAvailabilityUpdate,
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
    room_id: int,
    academic_term_id: int,
) -> None:
    room = require_by_id(db, Room, room_id, "Room")
    academic_term = require_by_id(
        db,
        AcademicTerm,
        academic_term_id,
        "Academic term",
    )
    if room.status != RoomStatus.ACTIVE:
        raise BusinessRuleError(
            "Room availability can only be defined for an active room.",
            details={"room_id": room.id, "room_status": room.status},
        )
    require_active(academic_term, "Academic term")


def get_room_availability(
    db: Session,
    room_availability_id: int,
) -> RoomAvailability:
    return require_by_id(
        db,
        RoomAvailability,
        room_availability_id,
        "Room availability",
    )


def list_room_availabilities(
    db: Session,
    pagination: PaginationParams,
    *,
    room_id: int | None = None,
    academic_term_id: int | None = None,
) -> PaginatedResponse[RoomAvailabilityRead]:
    filters = []
    if room_id is not None:
        require_by_id(db, Room, room_id, "Room")
        filters.append(RoomAvailability.room_id == room_id)
    if academic_term_id is not None:
        require_by_id(db, AcademicTerm, academic_term_id, "Academic term")
        filters.append(RoomAvailability.academic_term_id == academic_term_id)

    statement = (
        select(RoomAvailability)
        .where(*filters)
        .order_by(
            RoomAvailability.room_id,
            RoomAvailability.academic_term_id,
            RoomAvailability.day_of_week,
            RoomAvailability.start_time,
        )
    )
    count_statement = (
        select(func.count()).select_from(RoomAvailability).where(*filters)
    )
    rows, total = paginated_rows(db, statement, count_statement, pagination)
    return PaginatedResponse[RoomAvailabilityRead](
        items=[RoomAvailabilityRead.model_validate(row) for row in rows],
        total=total,
        page=pagination.page,
        page_size=pagination.page_size,
    )


def create_room_availability(
    db: Session,
    payload: RoomAvailabilityCreate,
) -> RoomAvailability:
    _validate_parents(
        db,
        room_id=payload.room_id,
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
        RoomAvailability,
        owner_field="room_id",
        owner_id=payload.room_id,
        academic_term_id=payload.academic_term_id,
        day_of_week=payload.day_of_week,
        start_time=payload.start_time,
        end_time=payload.end_time,
        resource_name="Room availability",
    )

    availability = RoomAvailability(**payload.model_dump())
    db.add(availability)
    return commit_and_refresh(db, availability)


def update_room_availability(
    db: Session,
    room_availability_id: int,
    payload: RoomAvailabilityUpdate,
) -> RoomAvailability:
    availability = get_room_availability(db, room_availability_id)
    changes = validated_changes(
        payload,
        non_nullable_fields=(
            "room_id",
            "academic_term_id",
            "day_of_week",
            "start_time",
            "end_time",
            "availability_type",
        ),
    )
    room_id = changes.get("room_id", availability.room_id)
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
        room_id=room_id,
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
        RoomAvailability,
        owner_field="room_id",
        owner_id=room_id,
        academic_term_id=academic_term_id,
        day_of_week=day_of_week,
        start_time=start_time,
        end_time=end_time,
        resource_name="Room availability",
        exclude_id=availability.id,
    )

    apply_changes(availability, changes)
    return commit_and_refresh(db, availability)


def delete_room_availability(
    db: Session,
    room_availability_id: int,
) -> MessageResponse:
    availability = get_room_availability(db, room_availability_id)
    commit_delete(db, availability)
    return MessageResponse(message="Room availability deleted successfully.")
