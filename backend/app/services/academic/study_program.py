from app.core.exceptions import BusinessRuleError, ResourceInUseError
from app.models.course_offering import CourseOffering
from app.models.curriculum_course import CurriculumCourse
from app.models.faculty import Faculty
from app.models.level import Level
from app.models.program_room_preference import ProgramRoomPreference
from app.models.program_semester import ProgramSemester
from app.models.student_group import StudentGroup
from app.models.study_program import StudyProgram
from app.schemas.common import MessageResponse, PaginatedResponse, PaginationParams
from app.schemas.study_program import (
    StudyProgramCreate,
    StudyProgramRead,
    StudyProgramUpdate,
)
from app.services.academic._common import (
    apply_changes,
    commit_and_refresh,
    ensure_unique,
    normalize_code,
    paginated_rows,
    require_active,
    require_by_id,
    validated_changes,
)
from sqlalchemy import func, select
from sqlalchemy.orm import Session


def _validate_parents(
    db: Session,
    faculty_id: int,
    level_id: int,
    *,
    require_active_parents: bool,
) -> Level:
    faculty = require_by_id(db, Faculty, faculty_id, "Faculty")
    level = require_by_id(db, Level, level_id, "Level")
    if require_active_parents:
        require_active(faculty, "Faculty")
        require_active(level, "Level")
    return level


def _ensure_structure_is_mutable(db: Session, study_program_id: int) -> None:
    student_group_id = db.scalar(
        select(StudentGroup.id)
        .join(
            ProgramSemester,
            ProgramSemester.id == StudentGroup.program_semester_id,
        )
        .where(ProgramSemester.study_program_id == study_program_id)
        .limit(1)
    )
    if student_group_id is not None:
        raise ResourceInUseError(
            "A study program with student groups cannot be reassigned.",
            details={
                "study_program_id": study_program_id,
                "student_group_id": student_group_id,
            },
        )

    course_offering_id = db.scalar(
        select(CourseOffering.id)
        .join(
            CurriculumCourse,
            CurriculumCourse.id == CourseOffering.curriculum_course_id,
        )
        .join(
            ProgramSemester,
            ProgramSemester.id == CurriculumCourse.program_semester_id,
        )
        .where(ProgramSemester.study_program_id == study_program_id)
        .limit(1)
    )
    if course_offering_id is not None:
        raise ResourceInUseError(
            "A study program with course offerings cannot be reassigned.",
            details={
                "study_program_id": study_program_id,
                "course_offering_id": course_offering_id,
            },
        )


def _ensure_can_be_deactivated(db: Session, study_program_id: int) -> None:
    active_semester_id = db.scalar(
        select(ProgramSemester.id)
        .where(
            ProgramSemester.study_program_id == study_program_id,
            ProgramSemester.is_active.is_(True),
        )
        .limit(1)
    )
    if active_semester_id is not None:
        raise ResourceInUseError(
            "Study program cannot be deactivated while it has active semesters.",
            details={
                "study_program_id": study_program_id,
                "program_semester_id": active_semester_id,
            },
        )

    active_preference_id = db.scalar(
        select(ProgramRoomPreference.id)
        .where(
            ProgramRoomPreference.study_program_id == study_program_id,
            ProgramRoomPreference.is_active.is_(True),
        )
        .limit(1)
    )
    if active_preference_id is not None:
        raise ResourceInUseError(
            "Study program cannot be deactivated while room preferences are active.",
            details={
                "study_program_id": study_program_id,
                "program_room_preference_id": active_preference_id,
            },
        )


def get_study_program(db: Session, study_program_id: int) -> StudyProgram:
    return require_by_id(db, StudyProgram, study_program_id, "Study program")


def list_study_programs(
    db: Session,
    pagination: PaginationParams,
    *,
    faculty_id: int | None = None,
    level_id: int | None = None,
    include_inactive: bool = False,
) -> PaginatedResponse[StudyProgramRead]:
    filters = []
    if faculty_id is not None:
        require_by_id(db, Faculty, faculty_id, "Faculty")
        filters.append(StudyProgram.faculty_id == faculty_id)
    if level_id is not None:
        require_by_id(db, Level, level_id, "Level")
        filters.append(StudyProgram.level_id == level_id)
    if not include_inactive:
        filters.append(StudyProgram.is_active.is_(True))

    statement = select(StudyProgram).where(*filters).order_by(StudyProgram.id)
    count_statement = select(func.count()).select_from(StudyProgram).where(*filters)
    rows, total = paginated_rows(db, statement, count_statement, pagination)
    return PaginatedResponse[StudyProgramRead](
        items=[StudyProgramRead.model_validate(row) for row in rows],
        total=total,
        page=pagination.page,
        page_size=pagination.page_size,
    )


def create_study_program(
    db: Session,
    payload: StudyProgramCreate,
) -> StudyProgram:
    _validate_parents(
        db,
        payload.faculty_id,
        payload.level_id,
        require_active_parents=payload.is_active,
    )
    values = payload.model_dump()
    values["code"] = normalize_code(payload.code)
    ensure_unique(
        db,
        StudyProgram,
        "Study program",
        ["faculty_id", "level_id", "code"],
        StudyProgram.faculty_id == payload.faculty_id,
        StudyProgram.level_id == payload.level_id,
        func.upper(StudyProgram.code) == values["code"],
    )
    study_program = StudyProgram(**values)
    db.add(study_program)
    return commit_and_refresh(db, study_program)


def update_study_program(
    db: Session,
    study_program_id: int,
    payload: StudyProgramUpdate,
) -> StudyProgram:
    study_program = get_study_program(db, study_program_id)
    changes = validated_changes(
        payload,
        non_nullable_fields=(
            "faculty_id",
            "level_id",
            "code",
            "name",
            "is_active",
        ),
    )
    faculty_id = changes.get("faculty_id", study_program.faculty_id)
    level_id = changes.get("level_id", study_program.level_id)
    if "code" in changes:
        changes["code"] = normalize_code(changes["code"])
    code = changes.get("code", study_program.code)
    final_is_active = changes.get("is_active", study_program.is_active)
    level = _validate_parents(
        db,
        faculty_id,
        level_id,
        require_active_parents=final_is_active,
    )

    ensure_unique(
        db,
        StudyProgram,
        "Study program",
        ["faculty_id", "level_id", "code"],
        StudyProgram.faculty_id == faculty_id,
        StudyProgram.level_id == level_id,
        func.upper(StudyProgram.code) == code,
        exclude_id=study_program.id,
    )

    highest_semester = db.scalar(
        select(func.max(ProgramSemester.semester_number)).where(
            ProgramSemester.study_program_id == study_program.id
        )
    )
    if highest_semester is not None and highest_semester > level.semester_count:
        raise BusinessRuleError(
            "The selected level has fewer semesters than this program already uses.",
            details={
                "study_program_id": study_program.id,
                "highest_existing_semester": highest_semester,
                "level_semester_count": level.semester_count,
            },
        )

    if faculty_id != study_program.faculty_id or level_id != study_program.level_id:
        _ensure_structure_is_mutable(db, study_program.id)
    if changes.get("is_active") is False and study_program.is_active:
        _ensure_can_be_deactivated(db, study_program.id)

    apply_changes(study_program, changes)
    return commit_and_refresh(db, study_program)


def delete_study_program(
    db: Session,
    study_program_id: int,
) -> MessageResponse:
    study_program = get_study_program(db, study_program_id)
    _ensure_can_be_deactivated(db, study_program.id)
    study_program.is_active = False
    commit_and_refresh(db, study_program)
    return MessageResponse(message="Study program deactivated successfully.")
