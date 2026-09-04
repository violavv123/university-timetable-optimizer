from app.core.exceptions import BusinessRuleError, ResourceInUseError
from app.models.curriculum_course import CurriculumCourse
from app.models.elective_group import ElectiveGroup
from app.models.program_semester import ProgramSemester
from app.schemas.common import MessageResponse, PaginatedResponse, PaginationParams
from app.schemas.elective_group import (
    ElectiveGroupCreate,
    ElectiveGroupRead,
    ElectiveGroupUpdate,
)
from app.services.academic.hierarchy import (
    require_active_program_semester_hierarchy,
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


def _require_program_semester(
    db: Session,
    program_semester_id: int,
    *,
    require_active_hierarchy: bool,
) -> ProgramSemester:
    program_semester = require_by_id(
        db,
        ProgramSemester,
        program_semester_id,
        "Program semester",
    )
    if require_active_hierarchy:
        require_active_program_semester_hierarchy(program_semester)
    return program_semester


def get_elective_group(db: Session, elective_group_id: int) -> ElectiveGroup:
    return require_by_id(
        db,
        ElectiveGroup,
        elective_group_id,
        "Elective group",
    )


def list_elective_groups(
    db: Session,
    pagination: PaginationParams,
    *,
    program_semester_id: int | None = None,
    include_inactive: bool = False,
) -> PaginatedResponse[ElectiveGroupRead]:
    filters = []
    if program_semester_id is not None:
        require_by_id(
            db,
            ProgramSemester,
            program_semester_id,
            "Program semester",
        )
        filters.append(ElectiveGroup.program_semester_id == program_semester_id)
    if not include_inactive:
        filters.append(ElectiveGroup.is_active.is_(True))

    statement = select(ElectiveGroup).where(*filters).order_by(ElectiveGroup.id)
    count_statement = select(func.count()).select_from(ElectiveGroup).where(*filters)
    rows, total = paginated_rows(db, statement, count_statement, pagination)
    return PaginatedResponse[ElectiveGroupRead](
        items=[ElectiveGroupRead.model_validate(row) for row in rows],
        total=total,
        page=pagination.page,
        page_size=pagination.page_size,
    )


def create_elective_group(
    db: Session,
    payload: ElectiveGroupCreate,
) -> ElectiveGroup:
    _require_program_semester(
        db,
        payload.program_semester_id,
        require_active_hierarchy=payload.is_active,
    )
    ensure_unique(
        db,
        ElectiveGroup,
        "Elective group",
        ["program_semester_id", "name"],
        ElectiveGroup.program_semester_id == payload.program_semester_id,
        ElectiveGroup.name == payload.name,
    )
    elective_group = ElectiveGroup(**payload.model_dump())
    db.add(elective_group)
    return commit_and_refresh(db, elective_group)


def update_elective_group(
    db: Session,
    elective_group_id: int,
    payload: ElectiveGroupUpdate,
) -> ElectiveGroup:
    elective_group = get_elective_group(db, elective_group_id)
    changes = validated_changes(
        payload,
        non_nullable_fields=(
            "program_semester_id",
            "name",
            "required_choices",
            "is_active",
        ),
    )
    program_semester_id = changes.get(
        "program_semester_id",
        elective_group.program_semester_id,
    )
    name = changes.get("name", elective_group.name)
    final_is_active = changes.get("is_active", elective_group.is_active)
    _require_program_semester(
        db,
        program_semester_id,
        require_active_hierarchy=final_is_active,
    )
    ensure_unique(
        db,
        ElectiveGroup,
        "Elective group",
        ["program_semester_id", "name"],
        ElectiveGroup.program_semester_id == program_semester_id,
        ElectiveGroup.name == name,
        exclude_id=elective_group.id,
    )

    mismatched_curriculum_course = db.scalar(
        select(CurriculumCourse.id)
        .where(
            CurriculumCourse.elective_group_id == elective_group.id,
            CurriculumCourse.program_semester_id != program_semester_id,
        )
        .limit(1)
    )
    if mismatched_curriculum_course is not None:
        raise BusinessRuleError(
            "The elective group cannot be moved away from its curriculum courses.",
            details={
                "elective_group_id": elective_group.id,
                "curriculum_course_id": mismatched_curriculum_course,
            },
        )

    if changes.get("is_active") is False and elective_group.is_active:
        active_curriculum_course_id = db.scalar(
            select(CurriculumCourse.id)
            .where(
                CurriculumCourse.elective_group_id == elective_group.id,
                CurriculumCourse.is_active.is_(True),
            )
            .limit(1)
        )
        if active_curriculum_course_id is not None:
            raise ResourceInUseError(
                "Elective group cannot be deactivated while courses use it.",
                details={
                    "elective_group_id": elective_group.id,
                    "curriculum_course_id": active_curriculum_course_id,
                },
            )

    apply_changes(elective_group, changes)
    return commit_and_refresh(db, elective_group)


def delete_elective_group(
    db: Session,
    elective_group_id: int,
) -> MessageResponse:
    elective_group = get_elective_group(db, elective_group_id)
    active_curriculum_course_id = db.scalar(
        select(CurriculumCourse.id)
        .where(
            CurriculumCourse.elective_group_id == elective_group.id,
            CurriculumCourse.is_active.is_(True),
        )
        .limit(1)
    )
    if active_curriculum_course_id is not None:
        raise ResourceInUseError(
            "Elective group cannot be deactivated while courses use it.",
            details={
                "elective_group_id": elective_group.id,
                "curriculum_course_id": active_curriculum_course_id,
            },
        )

    elective_group.is_active = False
    commit_and_refresh(db, elective_group)
    return MessageResponse(message="Elective group deactivated successfully.")
