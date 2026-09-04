from datetime import datetime, time

from app.core.exceptions import BusinessRuleError, ResourceInUseError
from app.models.scheduling_profile import SchedulingProfile
from app.models.time_slot import TimeSlot
from app.models.timetable_run import TimetableRun
from app.schemas.common import MessageResponse, PaginatedResponse, PaginationParams
from app.schemas.time_slot import TimeSlotCreate, TimeSlotRead, TimeSlotUpdate
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


def _minutes_between(start_time: time, end_time: time) -> int:
    start = datetime.combine(datetime.min.date(), start_time)
    end = datetime.combine(datetime.min.date(), end_time)
    return int((end - start).total_seconds() // 60)


def _ensure_profile_has_no_runs(
    db: Session,
    scheduling_profile_id: int,
) -> None:
    timetable_run_id = db.scalar(
        select(TimetableRun.id)
        .where(TimetableRun.scheduling_profile_id == scheduling_profile_id)
        .limit(1)
    )
    if timetable_run_id is not None:
        raise ResourceInUseError(
            "Time-slot configuration is immutable after the profile is used by a run.",
            details={
                "scheduling_profile_id": scheduling_profile_id,
                "timetable_run_id": timetable_run_id,
            },
        )


def _validate_slot(
    db: Session,
    *,
    scheduling_profile_id: int,
    day_of_week: int,
    slot_index: int,
    start_time: time,
    end_time: time,
    final_is_active: bool,
    exclude_id: int | None = None,
) -> SchedulingProfile:
    profile = require_by_id(
        db,
        SchedulingProfile,
        scheduling_profile_id,
        "Scheduling profile",
    )
    if final_is_active:
        require_active(profile, "Scheduling profile")
    if not 1 <= int(day_of_week) <= 7:
        raise BusinessRuleError("day_of_week must be between 1 and 7.")
    if slot_index < 0:
        raise BusinessRuleError("slot_index cannot be negative.")
    if end_time <= start_time:
        raise BusinessRuleError("end_time must be after start_time.")

    duration_minutes = _minutes_between(start_time, end_time)
    if duration_minutes != profile.slot_minutes:
        raise BusinessRuleError(
            "A time slot's duration must equal the profile's slot_minutes.",
            details={
                "scheduling_profile_id": profile.id,
                "slot_minutes": profile.slot_minutes,
                "actual_duration_minutes": duration_minutes,
            },
        )

    statement = select(TimeSlot).where(
        TimeSlot.scheduling_profile_id == scheduling_profile_id,
        TimeSlot.day_of_week == day_of_week,
    )
    if exclude_id is not None:
        statement = statement.where(TimeSlot.id != exclude_id)
    for other_slot in db.scalars(statement).all():
        if other_slot.start_time < end_time and other_slot.end_time > start_time:
            raise BusinessRuleError(
                "Time slots in the same profile and day cannot overlap.",
                details={
                    "scheduling_profile_id": scheduling_profile_id,
                    "day_of_week": int(day_of_week),
                    "overlapping_time_slot_id": other_slot.id,
                },
            )
        if other_slot.slot_index < slot_index and other_slot.start_time >= start_time:
            raise BusinessRuleError(
                "slot_index order must follow chronological start-time order.",
                details={"conflicting_time_slot_id": other_slot.id},
            )
        if other_slot.slot_index > slot_index and other_slot.start_time <= start_time:
            raise BusinessRuleError(
                "slot_index order must follow chronological start-time order.",
                details={"conflicting_time_slot_id": other_slot.id},
            )
    return profile


def get_time_slot(db: Session, time_slot_id: int) -> TimeSlot:
    return require_by_id(db, TimeSlot, time_slot_id, "Time slot")


def list_time_slots(
    db: Session,
    pagination: PaginationParams,
    *,
    scheduling_profile_id: int | None = None,
    day_of_week: int | None = None,
    include_inactive: bool = False,
) -> PaginatedResponse[TimeSlotRead]:
    filters = []
    if scheduling_profile_id is not None:
        require_by_id(
            db,
            SchedulingProfile,
            scheduling_profile_id,
            "Scheduling profile",
        )
        filters.append(TimeSlot.scheduling_profile_id == scheduling_profile_id)
    if day_of_week is not None:
        if not 1 <= int(day_of_week) <= 7:
            raise BusinessRuleError("day_of_week must be between 1 and 7.")
        filters.append(TimeSlot.day_of_week == day_of_week)
    if not include_inactive:
        filters.append(TimeSlot.is_active.is_(True))

    statement = (
        select(TimeSlot)
        .where(*filters)
        .order_by(
            TimeSlot.scheduling_profile_id,
            TimeSlot.day_of_week,
            TimeSlot.slot_index,
        )
    )
    count_statement = select(func.count()).select_from(TimeSlot).where(*filters)
    rows, total = paginated_rows(db, statement, count_statement, pagination)
    return PaginatedResponse[TimeSlotRead](
        items=[TimeSlotRead.model_validate(row) for row in rows],
        total=total,
        page=pagination.page,
        page_size=pagination.page_size,
    )


def create_time_slot(db: Session, payload: TimeSlotCreate) -> TimeSlot:
    _ensure_profile_has_no_runs(db, payload.scheduling_profile_id)
    _validate_slot(
        db,
        scheduling_profile_id=payload.scheduling_profile_id,
        day_of_week=payload.day_of_week,
        slot_index=payload.slot_index,
        start_time=payload.start_time,
        end_time=payload.end_time,
        final_is_active=payload.is_active,
    )
    ensure_unique(
        db,
        TimeSlot,
        "Time slot",
        ["scheduling_profile_id", "day_of_week", "slot_index"],
        TimeSlot.scheduling_profile_id == payload.scheduling_profile_id,
        TimeSlot.day_of_week == payload.day_of_week,
        TimeSlot.slot_index == payload.slot_index,
    )
    ensure_unique(
        db,
        TimeSlot,
        "Time slot",
        ["scheduling_profile_id", "day_of_week", "start_time"],
        TimeSlot.scheduling_profile_id == payload.scheduling_profile_id,
        TimeSlot.day_of_week == payload.day_of_week,
        TimeSlot.start_time == payload.start_time,
    )

    time_slot = TimeSlot(**payload.model_dump())
    db.add(time_slot)
    return commit_and_refresh(db, time_slot)


def update_time_slot(
    db: Session,
    time_slot_id: int,
    payload: TimeSlotUpdate,
) -> TimeSlot:
    time_slot = get_time_slot(db, time_slot_id)
    changes = validated_changes(
        payload,
        non_nullable_fields=(
            "scheduling_profile_id",
            "day_of_week",
            "slot_index",
            "start_time",
            "end_time",
            "is_active",
        ),
    )
    original_profile_id = time_slot.scheduling_profile_id
    scheduling_profile_id = changes.get(
        "scheduling_profile_id",
        original_profile_id,
    )
    day_of_week = changes.get("day_of_week", time_slot.day_of_week)
    slot_index = changes.get("slot_index", time_slot.slot_index)
    start_time = changes.get("start_time", time_slot.start_time)
    end_time = changes.get("end_time", time_slot.end_time)
    final_is_active = changes.get("is_active", time_slot.is_active)

    _ensure_profile_has_no_runs(db, original_profile_id)
    if scheduling_profile_id != original_profile_id:
        _ensure_profile_has_no_runs(db, scheduling_profile_id)
    _validate_slot(
        db,
        scheduling_profile_id=scheduling_profile_id,
        day_of_week=day_of_week,
        slot_index=slot_index,
        start_time=start_time,
        end_time=end_time,
        final_is_active=final_is_active,
        exclude_id=time_slot.id,
    )
    ensure_unique(
        db,
        TimeSlot,
        "Time slot",
        ["scheduling_profile_id", "day_of_week", "slot_index"],
        TimeSlot.scheduling_profile_id == scheduling_profile_id,
        TimeSlot.day_of_week == day_of_week,
        TimeSlot.slot_index == slot_index,
        exclude_id=time_slot.id,
    )
    ensure_unique(
        db,
        TimeSlot,
        "Time slot",
        ["scheduling_profile_id", "day_of_week", "start_time"],
        TimeSlot.scheduling_profile_id == scheduling_profile_id,
        TimeSlot.day_of_week == day_of_week,
        TimeSlot.start_time == start_time,
        exclude_id=time_slot.id,
    )

    apply_changes(time_slot, changes)
    return commit_and_refresh(db, time_slot)


def delete_time_slot(db: Session, time_slot_id: int) -> MessageResponse:
    time_slot = get_time_slot(db, time_slot_id)
    _ensure_profile_has_no_runs(db, time_slot.scheduling_profile_id)
    time_slot.is_active = False
    commit_and_refresh(db, time_slot)
    return MessageResponse(message="Time slot deactivated successfully.")
