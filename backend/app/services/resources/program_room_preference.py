from app.core.exceptions import BusinessRuleError, InvalidReferenceError
from app.models.enums import RoomStatus
from app.models.program_room_preference import ProgramRoomPreference
from app.models.room import Room
from app.models.study_program import StudyProgram
from app.schemas.common import MessageResponse, PaginatedResponse, PaginationParams
from app.schemas.program_room_preference import (
    ProgramRoomPreferenceCreate,
    ProgramRoomPreferenceRead,
    ProgramRoomPreferenceUpdate,
)
from app.services.academic.hierarchy import (
    require_active_study_program_hierarchy,
)
from app.services.common import (
    apply_changes,
    commit_and_refresh,
    ensure_unique,
    paginated_rows,
    require_by_id,
    validated_changes,
)
from sqlalchemy import func, select
from sqlalchemy.orm import Session


def _validate_configuration(
    db: Session,
    *,
    study_program_id: int,
    room_id: int,
    penalty_weight: int,
    require_active_parents: bool,
) -> None:
    if penalty_weight < 0:
        raise BusinessRuleError("penalty_weight cannot be negative.")

    study_program = require_by_id(
        db,
        StudyProgram,
        study_program_id,
        "Study program",
    )
    room = require_by_id(db, Room, room_id, "Room")
    if require_active_parents:
        require_active_study_program_hierarchy(study_program)
        if room.status != RoomStatus.ACTIVE:
            raise BusinessRuleError(
                "An active room preference requires an active room.",
                details={"room_id": room.id, "room_status": room.status},
            )

    if study_program.faculty_id != room.faculty_id:
        raise InvalidReferenceError(
            "The preferred room must belong to the study program's faculty.",
            details={
                "study_program_id": study_program.id,
                "study_program_faculty_id": study_program.faculty_id,
                "room_id": room.id,
                "room_faculty_id": room.faculty_id,
            },
        )


def get_program_room_preference(
    db: Session,
    program_room_preference_id: int,
) -> ProgramRoomPreference:
    return require_by_id(
        db,
        ProgramRoomPreference,
        program_room_preference_id,
        "Program room preference",
    )


def list_program_room_preferences(
    db: Session,
    pagination: PaginationParams,
    *,
    study_program_id: int | None = None,
    room_id: int | None = None,
    include_inactive: bool = False,
) -> PaginatedResponse[ProgramRoomPreferenceRead]:
    filters = []
    if study_program_id is not None:
        require_by_id(db, StudyProgram, study_program_id, "Study program")
        filters.append(
            ProgramRoomPreference.study_program_id == study_program_id
        )
    if room_id is not None:
        require_by_id(db, Room, room_id, "Room")
        filters.append(ProgramRoomPreference.room_id == room_id)
    if not include_inactive:
        filters.append(ProgramRoomPreference.is_active.is_(True))

    statement = (
        select(ProgramRoomPreference)
        .where(*filters)
        .order_by(
            ProgramRoomPreference.study_program_id,
            ProgramRoomPreference.penalty_weight.desc(),
            ProgramRoomPreference.room_id,
        )
    )
    count_statement = (
        select(func.count()).select_from(ProgramRoomPreference).where(*filters)
    )
    rows, total = paginated_rows(db, statement, count_statement, pagination)
    return PaginatedResponse[ProgramRoomPreferenceRead](
        items=[ProgramRoomPreferenceRead.model_validate(row) for row in rows],
        total=total,
        page=pagination.page,
        page_size=pagination.page_size,
    )


def create_program_room_preference(
    db: Session,
    payload: ProgramRoomPreferenceCreate,
) -> ProgramRoomPreference:
    _validate_configuration(
        db,
        study_program_id=payload.study_program_id,
        room_id=payload.room_id,
        penalty_weight=payload.penalty_weight,
        require_active_parents=payload.is_active,
    )
    ensure_unique(
        db,
        ProgramRoomPreference,
        "Program room preference",
        ["study_program_id", "room_id"],
        ProgramRoomPreference.study_program_id == payload.study_program_id,
        ProgramRoomPreference.room_id == payload.room_id,
    )

    preference = ProgramRoomPreference(**payload.model_dump())
    db.add(preference)
    return commit_and_refresh(db, preference)


def update_program_room_preference(
    db: Session,
    program_room_preference_id: int,
    payload: ProgramRoomPreferenceUpdate,
) -> ProgramRoomPreference:
    preference = get_program_room_preference(db, program_room_preference_id)
    changes = validated_changes(
        payload,
        non_nullable_fields=(
            "study_program_id",
            "room_id",
            "penalty_weight",
            "is_active",
        ),
    )
    study_program_id = changes.get(
        "study_program_id",
        preference.study_program_id,
    )
    room_id = changes.get("room_id", preference.room_id)
    penalty_weight = changes.get(
        "penalty_weight",
        preference.penalty_weight,
    )
    final_is_active = changes.get("is_active", preference.is_active)

    _validate_configuration(
        db,
        study_program_id=study_program_id,
        room_id=room_id,
        penalty_weight=penalty_weight,
        require_active_parents=final_is_active,
    )
    ensure_unique(
        db,
        ProgramRoomPreference,
        "Program room preference",
        ["study_program_id", "room_id"],
        ProgramRoomPreference.study_program_id == study_program_id,
        ProgramRoomPreference.room_id == room_id,
        exclude_id=preference.id,
    )

    apply_changes(preference, changes)
    return commit_and_refresh(db, preference)


def delete_program_room_preference(
    db: Session,
    program_room_preference_id: int,
) -> MessageResponse:
    preference = get_program_room_preference(db, program_room_preference_id)
    preference.is_active = False
    commit_and_refresh(db, preference)
    return MessageResponse(message="Program room preference deactivated successfully.")
