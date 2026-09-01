from app.core.exceptions import ResourceInUseError
from app.models.enums import RoomStatus
from app.models.faculty import Faculty
from app.models.room import Room
from app.models.scheduling_profile import SchedulingProfile
from app.models.staff_member import StaffMember
from app.models.study_program import StudyProgram
from app.schemas.common import MessageResponse, PaginatedResponse, PaginationParams
from app.schemas.faculty import FacultyCreate, FacultyRead, FacultyUpdate
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


def get_faculty(db: Session, faculty_id: int) -> Faculty:
    return require_by_id(db, Faculty, faculty_id, "Faculty")


def _ensure_can_be_deactivated(db: Session, faculty_id: int) -> None:
    active_dependencies = (
        (
            "study program",
            StudyProgram.id,
            StudyProgram.faculty_id == faculty_id,
            StudyProgram.is_active.is_(True),
        ),
        (
            "staff member",
            StaffMember.id,
            StaffMember.faculty_id == faculty_id,
            StaffMember.is_active.is_(True),
        ),
        (
            "room",
            Room.id,
            Room.faculty_id == faculty_id,
            Room.status.in_([RoomStatus.ACTIVE, RoomStatus.MAINTENANCE]),
        ),
        (
            "scheduling profile",
            SchedulingProfile.id,
            SchedulingProfile.faculty_id == faculty_id,
            SchedulingProfile.is_active.is_(True),
        ),
    )
    for resource_name, identifier, *conditions in active_dependencies:
        dependent_id = db.scalar(select(identifier).where(*conditions).limit(1))
        if dependent_id is not None:
            raise ResourceInUseError(
                "Faculty cannot be deactivated while it has active dependents.",
                details={
                    "faculty_id": faculty_id,
                    "dependent_resource": resource_name,
                    "dependent_id": dependent_id,
                },
            )


def list_faculties(
    db: Session,
    pagination: PaginationParams,
    *,
    include_inactive: bool = False,
) -> PaginatedResponse[FacultyRead]:
    filters = [] if include_inactive else [Faculty.is_active.is_(True)]
    statement = select(Faculty).where(*filters).order_by(Faculty.id)
    count_statement = select(func.count()).select_from(Faculty).where(*filters)
    rows, total = paginated_rows(db, statement, count_statement, pagination)
    return PaginatedResponse[FacultyRead](
        items=[FacultyRead.model_validate(row) for row in rows],
        total=total,
        page=pagination.page,
        page_size=pagination.page_size,
    )


def create_faculty(db: Session, payload: FacultyCreate) -> Faculty:
    values = payload.model_dump()
    values["code"] = normalize_code(payload.code)
    ensure_unique(
        db,
        Faculty,
        "Faculty",
        ["code"],
        func.upper(Faculty.code) == values["code"],
    )
    faculty = Faculty(**values)
    db.add(faculty)
    return commit_and_refresh(db, faculty)


def update_faculty(
    db: Session,
    faculty_id: int,
    payload: FacultyUpdate,
) -> Faculty:
    faculty = get_faculty(db, faculty_id)
    changes = validated_changes(
        payload,
        non_nullable_fields=("code", "name", "is_active"),
    )

    if "code" in changes:
        changes["code"] = normalize_code(changes["code"])
        ensure_unique(
            db,
            Faculty,
            "Faculty",
            ["code"],
            func.upper(Faculty.code) == changes["code"],
            exclude_id=faculty.id,
        )

    if changes.get("is_active") is False and faculty.is_active:
        _ensure_can_be_deactivated(db, faculty.id)

    apply_changes(faculty, changes)
    return commit_and_refresh(db, faculty)


def delete_faculty(db: Session, faculty_id: int) -> MessageResponse:
    faculty = get_faculty(db, faculty_id)
    _ensure_can_be_deactivated(db, faculty.id)
    faculty.is_active = False
    commit_and_refresh(db, faculty)
    return MessageResponse(message="Faculty deactivated successfully.")
