from app.core.exceptions import BusinessRuleError, ResourceInUseError
from app.models.course import Course
from app.models.course_offering import CourseOffering
from app.models.course_session import CourseSession
from app.models.course_session_staff import CourseSessionStaff
from app.models.curriculum_course import CurriculumCourse
from app.models.enums import CourseOfferingStatus, TeachingRole
from app.models.staff_course import StaffCourse
from app.models.staff_member import StaffMember
from app.schemas.common import MessageResponse, PaginatedResponse, PaginationParams
from app.schemas.staff_course import (
    StaffCourseCreate,
    StaffCourseRead,
    StaffCourseUpdate,
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


def _validate_qualification(
    *,
    can_lecture: bool,
    can_assist: bool,
) -> None:
    if not can_lecture and not can_assist:
        raise BusinessRuleError(
            "A staff-course qualification must allow lecturing, assisting, or both."
        )


def _validate_parents(
    db: Session,
    *,
    staff_member_id: int,
    course_id: int,
    require_active_parents: bool,
) -> None:
    staff_member = require_by_id(db, StaffMember, staff_member_id, "Staff member")
    course = require_by_id(db, Course, course_id, "Course")
    if require_active_parents:
        require_active(staff_member, "Staff member")
        require_active(course, "Course")


def _open_assignments(
    db: Session,
    *,
    staff_member_id: int,
    course_id: int,
) -> list[tuple[int, TeachingRole]]:
    statement = (
        select(CourseSession.id, CourseSessionStaff.teaching_role)
        .join(
            CourseSessionStaff,
            CourseSessionStaff.course_session_id == CourseSession.id,
        )
        .join(
            CourseOffering,
            CourseOffering.id == CourseSession.course_offering_id,
        )
        .join(
            CurriculumCourse,
            CurriculumCourse.id == CourseOffering.curriculum_course_id,
        )
        .where(
            CourseSessionStaff.staff_member_id == staff_member_id,
            CurriculumCourse.course_id == course_id,
            CourseSession.is_active.is_(True),
            CourseOffering.status.in_(
                [CourseOfferingStatus.DRAFT, CourseOfferingStatus.READY]
            ),
        )
    )
    return list(db.execute(statement).tuples().all())


def _ensure_assignments_remain_valid(
    db: Session,
    *,
    staff_member_id: int,
    course_id: int,
    can_lecture: bool,
    can_assist: bool,
    final_is_active: bool,
) -> None:
    for course_session_id, teaching_role in _open_assignments(
        db,
        staff_member_id=staff_member_id,
        course_id=course_id,
    ):
        role_is_allowed = (
            teaching_role == TeachingRole.LECTURER and can_lecture
        ) or (
            teaching_role
            in {
                TeachingRole.NUMERICAL_INSTRUCTOR,
                TeachingRole.LAB_INSTRUCTOR,
            }
            and can_assist
        )
        if not final_is_active or not role_is_allowed:
            raise ResourceInUseError(
                "The qualification change would invalidate an open "
                "course-session assignment.",
                details={
                    "staff_member_id": staff_member_id,
                    "course_id": course_id,
                    "course_session_id": course_session_id,
                    "teaching_role": teaching_role,
                },
            )


def get_staff_course(db: Session, staff_course_id: int) -> StaffCourse:
    return require_by_id(db, StaffCourse, staff_course_id, "Staff course")


def list_staff_courses(
    db: Session,
    pagination: PaginationParams,
    *,
    staff_member_id: int | None = None,
    course_id: int | None = None,
    include_inactive: bool = False,
) -> PaginatedResponse[StaffCourseRead]:
    filters = []
    if staff_member_id is not None:
        require_by_id(db, StaffMember, staff_member_id, "Staff member")
        filters.append(StaffCourse.staff_member_id == staff_member_id)
    if course_id is not None:
        require_by_id(db, Course, course_id, "Course")
        filters.append(StaffCourse.course_id == course_id)
    if not include_inactive:
        filters.append(StaffCourse.is_active.is_(True))

    statement = (
        select(StaffCourse)
        .where(*filters)
        .order_by(StaffCourse.staff_member_id, StaffCourse.course_id)
    )
    count_statement = select(func.count()).select_from(StaffCourse).where(*filters)
    rows, total = paginated_rows(db, statement, count_statement, pagination)
    return PaginatedResponse[StaffCourseRead](
        items=[StaffCourseRead.model_validate(row) for row in rows],
        total=total,
        page=pagination.page,
        page_size=pagination.page_size,
    )


def create_staff_course(
    db: Session,
    payload: StaffCourseCreate,
) -> StaffCourse:
    _validate_qualification(
        can_lecture=payload.can_lecture,
        can_assist=payload.can_assist,
    )
    _validate_parents(
        db,
        staff_member_id=payload.staff_member_id,
        course_id=payload.course_id,
        require_active_parents=payload.is_active,
    )
    ensure_unique(
        db,
        StaffCourse,
        "Staff course",
        ["staff_member_id", "course_id"],
        StaffCourse.staff_member_id == payload.staff_member_id,
        StaffCourse.course_id == payload.course_id,
    )

    staff_course = StaffCourse(**payload.model_dump())
    db.add(staff_course)
    return commit_and_refresh(db, staff_course)


def update_staff_course(
    db: Session,
    staff_course_id: int,
    payload: StaffCourseUpdate,
) -> StaffCourse:
    staff_course = get_staff_course(db, staff_course_id)
    changes = validated_changes(
        payload,
        non_nullable_fields=(
            "staff_member_id",
            "course_id",
            "can_lecture",
            "can_assist",
            "is_active",
        ),
    )
    staff_member_id = changes.get(
        "staff_member_id",
        staff_course.staff_member_id,
    )
    course_id = changes.get("course_id", staff_course.course_id)
    can_lecture = changes.get("can_lecture", staff_course.can_lecture)
    can_assist = changes.get("can_assist", staff_course.can_assist)
    final_is_active = changes.get("is_active", staff_course.is_active)

    _validate_qualification(can_lecture=can_lecture, can_assist=can_assist)
    _validate_parents(
        db,
        staff_member_id=staff_member_id,
        course_id=course_id,
        require_active_parents=final_is_active,
    )
    ensure_unique(
        db,
        StaffCourse,
        "Staff course",
        ["staff_member_id", "course_id"],
        StaffCourse.staff_member_id == staff_member_id,
        StaffCourse.course_id == course_id,
        exclude_id=staff_course.id,
    )

    if (
        staff_member_id != staff_course.staff_member_id
        or course_id != staff_course.course_id
    ):
        assignments = _open_assignments(
            db,
            staff_member_id=staff_course.staff_member_id,
            course_id=staff_course.course_id,
        )
        if assignments:
            raise ResourceInUseError(
                "A qualification used by an open session cannot be reassigned.",
                details={
                    "staff_course_id": staff_course.id,
                    "course_session_id": assignments[0][0],
                },
            )
    else:
        _ensure_assignments_remain_valid(
            db,
            staff_member_id=staff_member_id,
            course_id=course_id,
            can_lecture=can_lecture,
            can_assist=can_assist,
            final_is_active=final_is_active,
        )

    apply_changes(staff_course, changes)
    return commit_and_refresh(db, staff_course)


def delete_staff_course(
    db: Session,
    staff_course_id: int,
) -> MessageResponse:
    staff_course = get_staff_course(db, staff_course_id)
    _ensure_assignments_remain_valid(
        db,
        staff_member_id=staff_course.staff_member_id,
        course_id=staff_course.course_id,
        can_lecture=staff_course.can_lecture,
        can_assist=staff_course.can_assist,
        final_is_active=False,
    )
    staff_course.is_active = False
    commit_and_refresh(db, staff_course)
    return MessageResponse(
        message="Staff-course qualification deactivated successfully."
    )
