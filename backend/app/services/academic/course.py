from app.core.exceptions import ResourceInUseError
from app.models.course import Course
from app.models.curriculum_course import CurriculumCourse
from app.models.staff_course import StaffCourse
from app.schemas.common import MessageResponse, PaginatedResponse, PaginationParams
from app.schemas.course import CourseCreate, CourseRead, CourseUpdate
from app.services.common import (
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


def get_course(db: Session, course_id: int) -> Course:
    return require_by_id(db, Course, course_id, "Course")


def _ensure_can_be_deactivated(db: Session, course_id: int) -> None:
    active_curriculum_course_id = db.scalar(
        select(CurriculumCourse.id)
        .where(
            CurriculumCourse.course_id == course_id,
            CurriculumCourse.is_active.is_(True),
        )
        .limit(1)
    )
    if active_curriculum_course_id is not None:
        raise ResourceInUseError(
            "Course cannot be deactivated while it is used by an active curriculum.",
            details={
                "course_id": course_id,
                "curriculum_course_id": active_curriculum_course_id,
            },
        )

    active_staff_course_id = db.scalar(
        select(StaffCourse.id)
        .where(
            StaffCourse.course_id == course_id,
            StaffCourse.is_active.is_(True),
        )
        .limit(1)
    )
    if active_staff_course_id is not None:
        raise ResourceInUseError(
            "Course cannot be deactivated while staff qualifications use it.",
            details={
                "course_id": course_id,
                "staff_course_id": active_staff_course_id,
            },
        )


def list_courses(
    db: Session,
    pagination: PaginationParams,
    *,
    include_inactive: bool = False,
) -> PaginatedResponse[CourseRead]:
    filters = [] if include_inactive else [Course.is_active.is_(True)]
    statement = select(Course).where(*filters).order_by(Course.id)
    count_statement = select(func.count()).select_from(Course).where(*filters)
    rows, total = paginated_rows(db, statement, count_statement, pagination)
    return PaginatedResponse[CourseRead](
        items=[CourseRead.model_validate(row) for row in rows],
        total=total,
        page=pagination.page,
        page_size=pagination.page_size,
    )


def create_course(db: Session, payload: CourseCreate) -> Course:
    values = payload.model_dump()
    values["code"] = normalize_code(payload.code)
    ensure_unique(
        db,
        Course,
        "Course",
        ["code"],
        func.upper(Course.code) == values["code"],
    )
    course = Course(**values)
    db.add(course)
    return commit_and_refresh(db, course)


def update_course(db: Session, course_id: int, payload: CourseUpdate) -> Course:
    course = get_course(db, course_id)
    changes = validated_changes(
        payload,
        non_nullable_fields=("code", "name", "is_active"),
    )

    if "code" in changes:
        changes["code"] = normalize_code(changes["code"])
        ensure_unique(
            db,
            Course,
            "Course",
            ["code"],
            func.upper(Course.code) == changes["code"],
            exclude_id=course.id,
        )

    if changes.get("is_active") is False and course.is_active:
        _ensure_can_be_deactivated(db, course.id)

    apply_changes(course, changes)
    return commit_and_refresh(db, course)


def delete_course(db: Session, course_id: int) -> MessageResponse:
    course = get_course(db, course_id)
    _ensure_can_be_deactivated(db, course.id)
    course.is_active = False
    commit_and_refresh(db, course)
    return MessageResponse(message="Course deactivated successfully.")
