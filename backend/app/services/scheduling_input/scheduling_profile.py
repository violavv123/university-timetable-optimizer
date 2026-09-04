from collections.abc import Mapping

from app.core.exceptions import BusinessRuleError, ResourceInUseError
from app.models.enums import TimetableRunStatus
from app.models.faculty import Faculty
from app.models.scheduling_profile import SchedulingProfile
from app.models.time_slot import TimeSlot
from app.models.timetable_run import TimetableRun
from app.schemas.common import MessageResponse, PaginatedResponse, PaginationParams
from app.schemas.scheduling_profile import (
    SchedulingProfileCreate,
    SchedulingProfileRead,
    SchedulingProfileUpdate,
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

POSITIVE_FIELDS = (
    "slot_minutes",
    "max_lecture_students",
    "max_numerical_students",
    "max_lab_students",
)
WEIGHT_FIELDS = (
    "preferred_room_weight",
    "historical_room_weight",
    "student_gap_weight",
    "staff_gap_weight",
    "late_hour_weight",
)


def _validate_values(values: Mapping[str, object]) -> None:
    for field_name in POSITIVE_FIELDS:
        raw_value = values[field_name]

        if isinstance(raw_value, bool) or not isinstance(raw_value, int):
            raise BusinessRuleError(
                f"{field_name} must be an integer.",
                details={
                    "field": field_name,
                    "value": raw_value,
                },
            )

        if raw_value <= 0:
            raise BusinessRuleError(
                f"{field_name} must be greater than zero.",
                details={
                    "field": field_name,
                    "value": raw_value,
                },
            )

    for field_name in WEIGHT_FIELDS:
        raw_value = values[field_name]

        if isinstance(raw_value, bool) or not isinstance(raw_value, int):
            raise BusinessRuleError(
                f"{field_name} must be an integer.",
                details={
                    "field": field_name,
                    "value": raw_value,
                },
            )

        if raw_value < 0:
            raise BusinessRuleError(
                f"{field_name} cannot be negative.",
                details={
                    "field": field_name,
                    "value": raw_value,
                },
            )


def _validate_faculty(
    db: Session,
    faculty_id: int,
    *,
    require_active_faculty: bool,
) -> None:
    faculty = require_by_id(db, Faculty, faculty_id, "Faculty")
    if require_active_faculty:
        require_active(faculty, "Faculty")


def _ensure_structure_is_mutable(
    db: Session,
    scheduling_profile_id: int,
) -> None:
    time_slot_id = db.scalar(
        select(TimeSlot.id).where(TimeSlot.scheduling_profile_id == scheduling_profile_id).limit(1)
    )
    if time_slot_id is not None:
        raise ResourceInUseError(
            "A scheduling profile with time slots cannot change faculty or slot size.",
            details={
                "scheduling_profile_id": scheduling_profile_id,
                "time_slot_id": time_slot_id,
            },
        )

    timetable_run_id = db.scalar(
        select(TimetableRun.id)
        .where(TimetableRun.scheduling_profile_id == scheduling_profile_id)
        .limit(1)
    )
    if timetable_run_id is not None:
        raise ResourceInUseError(
            "A scheduling profile used by a timetable run cannot be structurally changed.",
            details={
                "scheduling_profile_id": scheduling_profile_id,
                "timetable_run_id": timetable_run_id,
            },
        )


def _ensure_can_be_deactivated(
    db: Session,
    scheduling_profile_id: int,
) -> None:
    active_slot_id = db.scalar(
        select(TimeSlot.id)
        .where(
            TimeSlot.scheduling_profile_id == scheduling_profile_id,
            TimeSlot.is_active.is_(True),
        )
        .limit(1)
    )
    if active_slot_id is not None:
        raise ResourceInUseError(
            "A scheduling profile cannot be deactivated while it has active slots.",
            details={
                "scheduling_profile_id": scheduling_profile_id,
                "time_slot_id": active_slot_id,
            },
        )

    running_run_id = db.scalar(
        select(TimetableRun.id)
        .where(
            TimetableRun.scheduling_profile_id == scheduling_profile_id,
            TimetableRun.status.in_([TimetableRunStatus.PENDING, TimetableRunStatus.RUNNING]),
        )
        .limit(1)
    )
    if running_run_id is not None:
        raise ResourceInUseError(
            "A profile cannot be deactivated while timetable work is running.",
            details={
                "scheduling_profile_id": scheduling_profile_id,
                "timetable_run_id": running_run_id,
            },
        )


def get_scheduling_profile(
    db: Session,
    scheduling_profile_id: int,
) -> SchedulingProfile:
    return require_by_id(
        db,
        SchedulingProfile,
        scheduling_profile_id,
        "Scheduling profile",
    )


def list_scheduling_profiles(
    db: Session,
    pagination: PaginationParams,
    *,
    faculty_id: int | None = None,
    include_inactive: bool = False,
) -> PaginatedResponse[SchedulingProfileRead]:
    filters = []
    if faculty_id is not None:
        require_by_id(db, Faculty, faculty_id, "Faculty")
        filters.append(SchedulingProfile.faculty_id == faculty_id)
    if not include_inactive:
        filters.append(SchedulingProfile.is_active.is_(True))

    statement = (
        select(SchedulingProfile)
        .where(*filters)
        .order_by(SchedulingProfile.faculty_id, SchedulingProfile.name)
    )
    count_statement = select(func.count()).select_from(SchedulingProfile).where(*filters)
    rows, total = paginated_rows(db, statement, count_statement, pagination)
    return PaginatedResponse[SchedulingProfileRead](
        items=[SchedulingProfileRead.model_validate(row) for row in rows],
        total=total,
        page=pagination.page,
        page_size=pagination.page_size,
    )


def create_scheduling_profile(
    db: Session,
    payload: SchedulingProfileCreate,
) -> SchedulingProfile:
    values = payload.model_dump()
    values["name"] = " ".join(payload.name.split())
    if not values["name"]:
        raise BusinessRuleError("name cannot be blank.")
    _validate_values(values)
    _validate_faculty(
        db,
        payload.faculty_id,
        require_active_faculty=payload.is_active,
    )
    ensure_unique(
        db,
        SchedulingProfile,
        "Scheduling profile",
        ["faculty_id", "name"],
        SchedulingProfile.faculty_id == payload.faculty_id,
        func.lower(SchedulingProfile.name) == values["name"].lower(),
    )

    profile = SchedulingProfile(**values)
    db.add(profile)
    return commit_and_refresh(db, profile)


def update_scheduling_profile(
    db: Session,
    scheduling_profile_id: int,
    payload: SchedulingProfileUpdate,
) -> SchedulingProfile:
    profile = get_scheduling_profile(db, scheduling_profile_id)
    changes = validated_changes(
        payload,
        non_nullable_fields=(
            "faculty_id",
            "name",
            *POSITIVE_FIELDS,
            *WEIGHT_FIELDS,
            "is_active",
        ),
    )
    if "name" in changes:
        changes["name"] = " ".join(changes["name"].split())
        if not changes["name"]:
            raise BusinessRuleError("name cannot be blank.")

    final_values = {
        field_name: changes.get(field_name, getattr(profile, field_name))
        for field_name in (*POSITIVE_FIELDS, *WEIGHT_FIELDS)
    }
    _validate_values(final_values)
    faculty_id = changes.get("faculty_id", profile.faculty_id)
    name = changes.get("name", profile.name)
    final_is_active = changes.get("is_active", profile.is_active)
    _validate_faculty(
        db,
        faculty_id,
        require_active_faculty=final_is_active,
    )
    ensure_unique(
        db,
        SchedulingProfile,
        "Scheduling profile",
        ["faculty_id", "name"],
        SchedulingProfile.faculty_id == faculty_id,
        func.lower(SchedulingProfile.name) == name.lower(),
        exclude_id=profile.id,
    )

    structure_changed = (
        faculty_id != profile.faculty_id or final_values["slot_minutes"] != profile.slot_minutes
    )
    if structure_changed:
        _ensure_structure_is_mutable(db, profile.id)
    if changes.get("is_active") is False and profile.is_active:
        _ensure_can_be_deactivated(db, profile.id)

    apply_changes(profile, changes)
    return commit_and_refresh(db, profile)


def delete_scheduling_profile(
    db: Session,
    scheduling_profile_id: int,
) -> MessageResponse:
    profile = get_scheduling_profile(db, scheduling_profile_id)
    _ensure_can_be_deactivated(db, profile.id)
    profile.is_active = False
    commit_and_refresh(db, profile)
    return MessageResponse(message="Scheduling profile deactivated successfully.")
