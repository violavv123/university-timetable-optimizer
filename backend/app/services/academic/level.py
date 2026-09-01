from app.core.exceptions import BusinessRuleError, ResourceInUseError
from app.models.level import Level
from app.models.program_semester import ProgramSemester
from app.models.study_program import StudyProgram
from app.schemas.common import MessageResponse, PaginatedResponse, PaginationParams
from app.schemas.level import LevelCreate, LevelRead, LevelUpdate
from app.services.academic._common import (
    apply_changes,
    commit_and_refresh,
    ensure_unique,
    normalize_code,
    paginated_rows,
    require_by_id,
    validated_changes,
)
from sqlalchemy import func, select
from sqlalchemy.orm import Session


def get_level(db: Session, level_id: int) -> Level:
    return require_by_id(db, Level, level_id, "Level")


def _ensure_can_be_deactivated(db: Session, level_id: int) -> None:
    active_program_id = db.scalar(
        select(StudyProgram.id)
        .where(
            StudyProgram.level_id == level_id,
            StudyProgram.is_active.is_(True),
        )
        .limit(1)
    )
    if active_program_id is not None:
        raise ResourceInUseError(
            "Level cannot be deactivated while it has active study programs.",
            details={
                "level_id": level_id,
                "study_program_id": active_program_id,
            },
        )


def list_levels(
    db: Session,
    pagination: PaginationParams,
    *,
    include_inactive: bool = False,
) -> PaginatedResponse[LevelRead]:
    filters = [] if include_inactive else [Level.is_active.is_(True)]
    statement = select(Level).where(*filters).order_by(Level.id)
    count_statement = select(func.count()).select_from(Level).where(*filters)
    rows, total = paginated_rows(db, statement, count_statement, pagination)
    return PaginatedResponse[LevelRead](
        items=[LevelRead.model_validate(row) for row in rows],
        total=total,
        page=pagination.page,
        page_size=pagination.page_size,
    )


def create_level(db: Session, payload: LevelCreate) -> Level:
    values = payload.model_dump()
    values["code"] = normalize_code(payload.code)
    ensure_unique(
        db,
        Level,
        "Level",
        ["code"],
        func.upper(Level.code) == values["code"],
    )
    level = Level(**values)
    db.add(level)
    return commit_and_refresh(db, level)


def update_level(db: Session, level_id: int, payload: LevelUpdate) -> Level:
    level = get_level(db, level_id)
    changes = validated_changes(
        payload,
        non_nullable_fields=(
            "code",
            "name",
            "semester_count",
            "is_active",
        ),
    )

    if "code" in changes:
        changes["code"] = normalize_code(changes["code"])
        ensure_unique(
            db,
            Level,
            "Level",
            ["code"],
            func.upper(Level.code) == changes["code"],
            exclude_id=level.id,
        )

    new_semester_count = changes.get("semester_count", level.semester_count)
    highest_existing_semester = db.scalar(
        select(func.max(ProgramSemester.semester_number))
        .join(
            StudyProgram,
            StudyProgram.id == ProgramSemester.study_program_id,
        )
        .where(StudyProgram.level_id == level.id)
    )
    if highest_existing_semester is not None and highest_existing_semester > new_semester_count:
        raise BusinessRuleError(
            "semester_count cannot be lower than an existing program semester.",
            details={
                "level_id": level.id,
                "highest_existing_semester": highest_existing_semester,
                "requested_semester_count": new_semester_count,
            },
        )

    if changes.get("is_active") is False and level.is_active:
        _ensure_can_be_deactivated(db, level.id)

    apply_changes(level, changes)
    return commit_and_refresh(db, level)


def delete_level(db: Session, level_id: int) -> MessageResponse:
    level = get_level(db, level_id)
    _ensure_can_be_deactivated(db, level.id)
    level.is_active = False
    commit_and_refresh(db, level)
    return MessageResponse(message="Level deactivated successfully.")
