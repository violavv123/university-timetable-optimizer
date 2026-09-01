from decimal import Decimal

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.core.exceptions import (
    BusinessRuleError,
    InvalidReferenceError,
    ResourceInUseError,
)
from app.models.course import Course
from app.models.course_offering import CourseOffering
from app.models.curriculum_course import CurriculumCourse
from app.models.elective_group import ElectiveGroup
from app.models.enums import CourseOfferingStatus, CourseType
from app.models.program_semester import ProgramSemester
from app.schemas.common import MessageResponse, PaginatedResponse, PaginationParams
from app.schemas.curriculum_course import (
    CurriculumCourseCreate,
    CurriculumCourseRead,
    CurriculumCourseUpdate,
)
from app.services.academic._common import (
    apply_changes,
    commit_and_refresh,
    ensure_unique,
    paginated_rows,
    require_active,
    require_by_id,
    validated_changes,
)
from app.services.academic._hierarchy import (
    require_active_program_semester_hierarchy,
)


def _validate_curriculum_configuration(
    db: Session,
    *,
    program_semester_id: int,
    course_id: int,
    course_type: CourseType,
    elective_group_id: int | None,
    ects: Decimal,
    requires_timetable: bool,
    lecture_periods_per_week: int,
    numerical_periods_per_week: int,
    laboratory_periods_per_week: int,
    require_active_hierarchy: bool,
    exclude_id: int | None = None,
) -> None:
    program_semester = require_by_id(
        db,
        ProgramSemester,
        program_semester_id,
        "Program semester",
    )
    course = require_by_id(db, Course, course_id, "Course")
    if require_active_hierarchy:
        require_active_program_semester_hierarchy(program_semester)
        require_active(course, "Course")

    if ects <= 0:
        raise BusinessRuleError("ects must be greater than zero.")
    if ects > Decimal("30.0"):
        raise BusinessRuleError(
            "A curriculum course cannot exceed 30 ECTS.",
            details={"ects": ects},
        )

    total_periods = (
        lecture_periods_per_week
        + numerical_periods_per_week
        + laboratory_periods_per_week
    )
    if requires_timetable and total_periods <= 0:
        raise BusinessRuleError(
            "At least one weekly teaching period is required when "
            "requires_timetable is true.",
            details={
                "requires_timetable": requires_timetable,
                "total_periods_per_week": total_periods,
            },
        )

    if course_type == CourseType.MANDATORY:
        if elective_group_id is not None:
            raise BusinessRuleError(
                "Mandatory courses cannot belong to an elective group."
            )
        return

    if elective_group_id is None:
        raise BusinessRuleError(
            "Elective courses must belong to an elective group."
        )

    elective_group = require_by_id(
        db,
        ElectiveGroup,
        elective_group_id,
        "Elective group",
    )
    if require_active_hierarchy:
        require_active(elective_group, "Elective group")
    if elective_group.program_semester_id != program_semester_id:
        raise InvalidReferenceError(
            "The elective group and curriculum course must belong to the same "
            "program semester.",
            details={
                "elective_group_id": elective_group.id,
                "elective_group_program_semester_id": (
                    elective_group.program_semester_id
                ),
                "curriculum_program_semester_id": program_semester_id,
            },
        )

    if require_active_hierarchy:
        statement = select(CurriculumCourse.id).where(
            CurriculumCourse.elective_group_id == elective_group.id,
            CurriculumCourse.is_active.is_(True),
            CurriculumCourse.ects != ects,
        )
        if exclude_id is not None:
            statement = statement.where(CurriculumCourse.id != exclude_id)

        different_ects_course_id = db.scalar(statement.limit(1))
        if different_ects_course_id is not None:
            raise BusinessRuleError(
                "Active choices in one elective group must have equal ECTS.",
                details={
                    "elective_group_id": elective_group.id,
                    "curriculum_course_id": different_ects_course_id,
                    "requested_ects": ects,
                },
            )


def _get_course_offering_id(
    db: Session,
    curriculum_course_id: int,
    *,
    open_only: bool,
) -> int | None:
    statement = select(CourseOffering.id).where(
        CourseOffering.curriculum_course_id == curriculum_course_id,
    )
    if open_only:
        statement = statement.where(
            CourseOffering.status.in_(
                [CourseOfferingStatus.DRAFT, CourseOfferingStatus.READY]
            )
        )
    return db.scalar(statement.limit(1))


def get_curriculum_course(
    db: Session,
    curriculum_course_id: int,
) -> CurriculumCourse:
    return require_by_id(
        db,
        CurriculumCourse,
        curriculum_course_id,
        "Curriculum course",
    )


def list_curriculum_courses(
    db: Session,
    pagination: PaginationParams,
    *,
    program_semester_id: int | None = None,
    course_id: int | None = None,
    include_inactive: bool = False,
) -> PaginatedResponse[CurriculumCourseRead]:
    filters = []
    if program_semester_id is not None:
        require_by_id(
            db,
            ProgramSemester,
            program_semester_id,
            "Program semester",
        )
        filters.append(
            CurriculumCourse.program_semester_id == program_semester_id
        )
    if course_id is not None:
        require_by_id(db, Course, course_id, "Course")
        filters.append(CurriculumCourse.course_id == course_id)
    if not include_inactive:
        filters.append(CurriculumCourse.is_active.is_(True))

    statement = (
        select(CurriculumCourse)
        .where(*filters)
        .order_by(
            CurriculumCourse.program_semester_id,
            CurriculumCourse.course_id,
        )
    )
    count_statement = (
        select(func.count()).select_from(CurriculumCourse).where(*filters)
    )
    rows, total = paginated_rows(db, statement, count_statement, pagination)
    return PaginatedResponse[CurriculumCourseRead](
        items=[CurriculumCourseRead.model_validate(row) for row in rows],
        total=total,
        page=pagination.page,
        page_size=pagination.page_size,
    )


def create_curriculum_course(
    db: Session,
    payload: CurriculumCourseCreate,
) -> CurriculumCourse:
    _validate_curriculum_configuration(
        db,
        program_semester_id=payload.program_semester_id,
        course_id=payload.course_id,
        course_type=payload.course_type,
        elective_group_id=payload.elective_group_id,
        ects=payload.ects,
        requires_timetable=payload.requires_timetable,
        lecture_periods_per_week=payload.lecture_periods_per_week,
        numerical_periods_per_week=payload.numerical_periods_per_week,
        laboratory_periods_per_week=payload.laboratory_periods_per_week,
        require_active_hierarchy=payload.is_active,
    )
    ensure_unique(
        db,
        CurriculumCourse,
        "Curriculum course",
        ["program_semester_id", "course_id"],
        CurriculumCourse.program_semester_id == payload.program_semester_id,
        CurriculumCourse.course_id == payload.course_id,
    )

    curriculum_course = CurriculumCourse(**payload.model_dump())
    db.add(curriculum_course)
    return commit_and_refresh(db, curriculum_course)


def update_curriculum_course(
    db: Session,
    curriculum_course_id: int,
    payload: CurriculumCourseUpdate,
) -> CurriculumCourse:
    curriculum_course = get_curriculum_course(db, curriculum_course_id)
    changes = validated_changes(
        payload,
        non_nullable_fields=(
            "program_semester_id",
            "course_id",
            "course_type",
            "ects",
            "requires_timetable",
            "lecture_periods_per_week",
            "numerical_periods_per_week",
            "laboratory_periods_per_week",
            "is_active",
        ),
    )

    program_semester_id = changes.get(
        "program_semester_id",
        curriculum_course.program_semester_id,
    )
    course_id = changes.get("course_id", curriculum_course.course_id)
    course_type = changes.get("course_type", curriculum_course.course_type)
    elective_group_id = changes.get(
        "elective_group_id",
        curriculum_course.elective_group_id,
    )
    ects = changes.get("ects", curriculum_course.ects)
    requires_timetable = changes.get(
        "requires_timetable",
        curriculum_course.requires_timetable,
    )
    lecture_periods = changes.get(
        "lecture_periods_per_week",
        curriculum_course.lecture_periods_per_week,
    )
    numerical_periods = changes.get(
        "numerical_periods_per_week",
        curriculum_course.numerical_periods_per_week,
    )
    laboratory_periods = changes.get(
        "laboratory_periods_per_week",
        curriculum_course.laboratory_periods_per_week,
    )
    final_is_active = changes.get("is_active", curriculum_course.is_active)

    structural_fields = {
        "program_semester_id",
        "course_id",
        "course_type",
        "elective_group_id",
        "ects",
        "requires_timetable",
        "lecture_periods_per_week",
        "numerical_periods_per_week",
        "laboratory_periods_per_week",
    }
    if structural_fields.intersection(changes):
        course_offering_id = _get_course_offering_id(
            db,
            curriculum_course.id,
            open_only=False,
        )
        if course_offering_id is not None:
            raise ResourceInUseError(
                "A curriculum course with offerings cannot be structurally changed.",
                details={
                    "curriculum_course_id": curriculum_course.id,
                    "course_offering_id": course_offering_id,
                },
            )

    if changes.get("is_active") is False and curriculum_course.is_active:
        open_offering_id = _get_course_offering_id(
            db,
            curriculum_course.id,
            open_only=True,
        )
        if open_offering_id is not None:
            raise ResourceInUseError(
                "Curriculum course cannot be deactivated while offerings are open.",
                details={
                    "curriculum_course_id": curriculum_course.id,
                    "course_offering_id": open_offering_id,
                },
            )

    _validate_curriculum_configuration(
        db,
        program_semester_id=program_semester_id,
        course_id=course_id,
        course_type=course_type,
        elective_group_id=elective_group_id,
        ects=ects,
        requires_timetable=requires_timetable,
        lecture_periods_per_week=lecture_periods,
        numerical_periods_per_week=numerical_periods,
        laboratory_periods_per_week=laboratory_periods,
        require_active_hierarchy=final_is_active,
        exclude_id=curriculum_course.id,
    )
    ensure_unique(
        db,
        CurriculumCourse,
        "Curriculum course",
        ["program_semester_id", "course_id"],
        CurriculumCourse.program_semester_id == program_semester_id,
        CurriculumCourse.course_id == course_id,
        exclude_id=curriculum_course.id,
    )

    apply_changes(curriculum_course, changes)
    return commit_and_refresh(db, curriculum_course)


def delete_curriculum_course(
    db: Session,
    curriculum_course_id: int,
) -> MessageResponse:
    curriculum_course = get_curriculum_course(db, curriculum_course_id)
    open_offering_id = _get_course_offering_id(
        db,
        curriculum_course.id,
        open_only=True,
    )
    if open_offering_id is not None:
        raise ResourceInUseError(
            "Curriculum course cannot be deactivated while offerings are open.",
            details={
                "curriculum_course_id": curriculum_course.id,
                "course_offering_id": open_offering_id,
            },
        )

    curriculum_course.is_active = False
    commit_and_refresh(db, curriculum_course)
    return MessageResponse(message="Curriculum course deactivated successfully.")
