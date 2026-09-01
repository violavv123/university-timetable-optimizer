from app.core.exceptions import BusinessRuleError, ResourceInUseError
from app.models.course_offering import CourseOffering
from app.models.curriculum_course import CurriculumCourse
from app.models.elective_group import ElectiveGroup
from app.models.program_semester import ProgramSemester
from app.models.student_group import StudentGroup
from app.models.study_program import StudyProgram
from app.schemas.common import MessageResponse, PaginatedResponse, PaginationParams
from app.schemas.program_semester import (
    ProgramSemesterCreate,
    ProgramSemesterRead,
    ProgramSemesterUpdate,
)
from app.services.academic._common import (
    apply_changes,
    commit_and_refresh,
    ensure_unique,
    paginated_rows,
    require_by_id,
    validated_changes,
)
from app.services.academic._hierarchy import (
    require_active_study_program_hierarchy,
)
from sqlalchemy import func, select
from sqlalchemy.orm import Session


def _validate_semester_number(
    study_program: StudyProgram,
    semester_number: int,
) -> None:
    if semester_number > study_program.level.semester_count:
        raise BusinessRuleError(
            "semester_number exceeds the study program level limit.",
            details={
                "study_program_id": study_program.id,
                "semester_number": semester_number,
                "level_semester_count": study_program.level.semester_count,
            },
        )


def _ensure_structure_is_mutable(
    db: Session,
    program_semester_id: int,
) -> None:
    student_group_id = db.scalar(
        select(StudentGroup.id)
        .where(StudentGroup.program_semester_id == program_semester_id)
        .limit(1)
    )
    if student_group_id is not None:
        raise ResourceInUseError(
            "A program semester with student groups cannot be reassigned.",
            details={
                "program_semester_id": program_semester_id,
                "student_group_id": student_group_id,
            },
        )

    course_offering_id = db.scalar(
        select(CourseOffering.id)
        .join(
            CurriculumCourse,
            CurriculumCourse.id == CourseOffering.curriculum_course_id,
        )
        .where(CurriculumCourse.program_semester_id == program_semester_id)
        .limit(1)
    )
    if course_offering_id is not None:
        raise ResourceInUseError(
            "A program semester with course offerings cannot be reassigned.",
            details={
                "program_semester_id": program_semester_id,
                "course_offering_id": course_offering_id,
            },
        )


def _ensure_can_be_deactivated(
    db: Session,
    program_semester_id: int,
) -> None:
    active_dependencies = (
        (
            "elective group",
            ElectiveGroup.id,
            ElectiveGroup.program_semester_id == program_semester_id,
            ElectiveGroup.is_active.is_(True),
        ),
        (
            "curriculum course",
            CurriculumCourse.id,
            CurriculumCourse.program_semester_id == program_semester_id,
            CurriculumCourse.is_active.is_(True),
        ),
        (
            "student group",
            StudentGroup.id,
            StudentGroup.program_semester_id == program_semester_id,
            StudentGroup.is_active.is_(True),
        ),
    )
    for resource_name, identifier, *conditions in active_dependencies:
        dependent_id = db.scalar(select(identifier).where(*conditions).limit(1))
        if dependent_id is not None:
            raise ResourceInUseError(
                "Program semester cannot be deactivated with active dependents.",
                details={
                    "program_semester_id": program_semester_id,
                    "dependent_resource": resource_name,
                    "dependent_id": dependent_id,
                },
            )


def get_program_semester(
    db: Session,
    program_semester_id: int,
) -> ProgramSemester:
    return require_by_id(
        db,
        ProgramSemester,
        program_semester_id,
        "Program semester",
    )


def list_program_semesters(
    db: Session,
    pagination: PaginationParams,
    *,
    study_program_id: int | None = None,
    include_inactive: bool = False,
) -> PaginatedResponse[ProgramSemesterRead]:
    filters = []
    if study_program_id is not None:
        require_by_id(db, StudyProgram, study_program_id, "Study program")
        filters.append(ProgramSemester.study_program_id == study_program_id)
    if not include_inactive:
        filters.append(ProgramSemester.is_active.is_(True))

    statement = (
        select(ProgramSemester)
        .where(*filters)
        .order_by(ProgramSemester.study_program_id, ProgramSemester.semester_number)
    )
    count_statement = select(func.count()).select_from(ProgramSemester).where(*filters)
    rows, total = paginated_rows(db, statement, count_statement, pagination)
    return PaginatedResponse[ProgramSemesterRead](
        items=[ProgramSemesterRead.model_validate(row) for row in rows],
        total=total,
        page=pagination.page,
        page_size=pagination.page_size,
    )


def create_program_semester(
    db: Session,
    payload: ProgramSemesterCreate,
) -> ProgramSemester:
    study_program = require_by_id(
        db,
        StudyProgram,
        payload.study_program_id,
        "Study program",
    )
    _validate_semester_number(study_program, payload.semester_number)
    if payload.is_active:
        require_active_study_program_hierarchy(study_program)
    ensure_unique(
        db,
        ProgramSemester,
        "Program semester",
        ["study_program_id", "semester_number"],
        ProgramSemester.study_program_id == payload.study_program_id,
        ProgramSemester.semester_number == payload.semester_number,
    )

    program_semester = ProgramSemester(**payload.model_dump())
    db.add(program_semester)
    return commit_and_refresh(db, program_semester)


def update_program_semester(
    db: Session,
    program_semester_id: int,
    payload: ProgramSemesterUpdate,
) -> ProgramSemester:
    program_semester = get_program_semester(db, program_semester_id)
    changes = validated_changes(
        payload,
        non_nullable_fields=(
            "study_program_id",
            "semester_number",
            "is_active",
        ),
    )
    study_program_id = changes.get(
        "study_program_id",
        program_semester.study_program_id,
    )
    semester_number = changes.get(
        "semester_number",
        program_semester.semester_number,
    )
    study_program = require_by_id(
        db,
        StudyProgram,
        study_program_id,
        "Study program",
    )
    _validate_semester_number(study_program, semester_number)
    final_is_active = changes.get("is_active", program_semester.is_active)
    if final_is_active:
        require_active_study_program_hierarchy(study_program)

    if (
        study_program_id != program_semester.study_program_id
        or semester_number != program_semester.semester_number
    ):
        _ensure_structure_is_mutable(db, program_semester.id)
    if changes.get("is_active") is False and program_semester.is_active:
        _ensure_can_be_deactivated(db, program_semester.id)
    ensure_unique(
        db,
        ProgramSemester,
        "Program semester",
        ["study_program_id", "semester_number"],
        ProgramSemester.study_program_id == study_program_id,
        ProgramSemester.semester_number == semester_number,
        exclude_id=program_semester.id,
    )

    apply_changes(program_semester, changes)
    return commit_and_refresh(db, program_semester)


def delete_program_semester(
    db: Session,
    program_semester_id: int,
) -> MessageResponse:
    program_semester = get_program_semester(db, program_semester_id)
    _ensure_can_be_deactivated(db, program_semester.id)
    program_semester.is_active = False
    commit_and_refresh(db, program_semester)
    return MessageResponse(message="Program semester deactivated successfully.")
