from datetime import time

from app.core.exceptions import BusinessRuleError
from app.models.course_session import CourseSession
from app.models.course_session_time_constraint import (
    CourseSessionTimeConstraint,
)
from app.models.enums import TimeConstraintType
from app.schemas.common import MessageResponse, PaginatedResponse, PaginationParams
from app.schemas.course_session_time_constraint import (
    CourseSessionTimeConstraintCreate,
    CourseSessionTimeConstraintRead,
    CourseSessionTimeConstraintUpdate,
)
from app.services.common import (
    apply_changes,
    commit_and_refresh,
    commit_delete,
    paginated_rows,
    require_by_id,
    validated_changes,
)
from app.services.scheduling_input.guards import require_editable_session
from sqlalchemy import func, select
from sqlalchemy.orm import Session

MASTER_LEVEL_CODE = "MSC"
MASTER_LATEST_END = time(20, 0)


def _days_intersect(first_day: int | None, second_day: int | None) -> bool:
    return first_day is None or second_day is None or first_day == second_day


def _windows_overlap(
    first_start: time,
    first_end: time,
    second_start: time,
    second_end: time,
) -> bool:
    return first_start < second_end and first_end > second_start


def _contains(
    outer_start: time,
    outer_end: time,
    inner_start: time,
    inner_end: time,
) -> bool:
    return outer_start <= inner_start and outer_end >= inner_end


def _allowed_window_applies(
    allowed_day: int | None,
    constrained_day: int | None,
) -> bool:
    if constrained_day is None:
        return allowed_day is None
    return allowed_day is None or allowed_day == constrained_day


def _validate_weight(
    constraint_type: TimeConstraintType,
    preference_weight: int | None,
) -> None:
    if constraint_type == TimeConstraintType.PREFERRED_WINDOW:
        if preference_weight is None:
            raise BusinessRuleError("PREFERRED_WINDOW requires preference_weight.")
        if preference_weight < 0:
            raise BusinessRuleError("preference_weight cannot be negative.")
    elif preference_weight is not None:
        raise BusinessRuleError("Hard time constraints must not have preference_weight.")


def _validate_against_existing(
    db: Session,
    *,
    session: CourseSession,
    day_of_week: int | None,
    start_time: time,
    end_time: time,
    constraint_type: TimeConstraintType,
    exclude_id: int | None = None,
) -> None:
    statement = select(CourseSessionTimeConstraint).where(
        CourseSessionTimeConstraint.course_session_id == session.id
    )
    if exclude_id is not None:
        statement = statement.where(CourseSessionTimeConstraint.id != exclude_id)
    existing_constraints = list(db.scalars(statement).all())

    allowed_constraints = [
        constraint
        for constraint in existing_constraints
        if constraint.constraint_type == TimeConstraintType.ALLOWED_WINDOW
        and _allowed_window_applies(constraint.day_of_week, day_of_week)
    ]
    fixed_constraints = [
        constraint
        for constraint in existing_constraints
        if constraint.constraint_type == TimeConstraintType.FIXED_WINDOW
    ]

    if constraint_type == TimeConstraintType.FIXED_WINDOW and fixed_constraints:
        raise BusinessRuleError(
            "A course session can have only one fixed time window.",
            details={
                "course_session_id": session.id,
                "fixed_constraint_id": fixed_constraints[0].id,
            },
        )

    for other in existing_constraints:
        if not _days_intersect(day_of_week, other.day_of_week):
            continue
        overlaps = _windows_overlap(
            start_time,
            end_time,
            other.start_time,
            other.end_time,
        )
        if constraint_type == other.constraint_type and overlaps:
            raise BusinessRuleError(
                "Overlapping time constraints of the same type are not allowed.",
                details={
                    "course_session_id": session.id,
                    "conflicting_constraint_id": other.id,
                },
            )
        hard_or_soft_conflict = (
            constraint_type
            in {
                TimeConstraintType.FIXED_WINDOW,
                TimeConstraintType.PREFERRED_WINDOW,
            }
            and other.constraint_type == TimeConstraintType.FORBIDDEN_WINDOW
        ) or (
            constraint_type == TimeConstraintType.FORBIDDEN_WINDOW
            and other.constraint_type
            in {
                TimeConstraintType.FIXED_WINDOW,
                TimeConstraintType.PREFERRED_WINDOW,
            }
        )
        if overlaps and hard_or_soft_conflict:
            raise BusinessRuleError(
                "Fixed or preferred windows cannot overlap forbidden windows.",
                details={
                    "course_session_id": session.id,
                    "conflicting_constraint_id": other.id,
                },
            )

    if (
        constraint_type
        in {
            TimeConstraintType.FIXED_WINDOW,
            TimeConstraintType.PREFERRED_WINDOW,
        }
        and allowed_constraints
    ):
        if not any(
            _contains(
                constraint.start_time,
                constraint.end_time,
                start_time,
                end_time,
            )
            for constraint in allowed_constraints
        ):
            raise BusinessRuleError(
                "Fixed and preferred windows must fit inside an allowed window.",
                details={"course_session_id": session.id},
            )

    if constraint_type == TimeConstraintType.ALLOWED_WINDOW:
        for fixed in fixed_constraints:
            applies = _allowed_window_applies(day_of_week, fixed.day_of_week)
            contains_fixed = _contains(
                start_time,
                end_time,
                fixed.start_time,
                fixed.end_time,
            )
            if applies and not contains_fixed:
                raise BusinessRuleError(
                    "An allowed window cannot exclude the existing fixed window.",
                    details={
                        "course_session_id": session.id,
                        "fixed_constraint_id": fixed.id,
                    },
                )


def _validate_constraint(
    db: Session,
    *,
    session: CourseSession,
    day_of_week: int | None,
    start_time: time,
    end_time: time,
    constraint_type: TimeConstraintType,
    preference_weight: int | None,
    exclude_id: int | None = None,
) -> None:
    if day_of_week is not None and not 1 <= int(day_of_week) <= 7:
        raise BusinessRuleError("day_of_week must be between 1 and 7 or null.")
    if end_time <= start_time:
        raise BusinessRuleError("end_time must be after start_time.")
    if constraint_type == TimeConstraintType.FIXED_WINDOW and day_of_week is None:
        raise BusinessRuleError("FIXED_WINDOW requires a specific day_of_week.")

    if constraint_type == TimeConstraintType.FIXED_WINDOW and session.weekly_frequency != 1:
        raise BusinessRuleError(
            "FIXED_WINDOW requires weekly_frequency=1 because the current "
            "constraint schema cannot identify a particular occurrence.",
            details={
                "course_session_id": session.id,
                "weekly_frequency": session.weekly_frequency,
            },
        )

    _validate_weight(constraint_type, preference_weight)

    program_semester = session.course_offering.curriculum_course.program_semester
    level_code = program_semester.study_program.level.code
    if (
        level_code.strip().upper() == MASTER_LEVEL_CODE
        and constraint_type == TimeConstraintType.FIXED_WINDOW
        and end_time > MASTER_LATEST_END
    ):
        raise BusinessRuleError(
            "Master sessions must finish by 20:00.",
            details={"course_session_id": session.id, "end_time": end_time},
        )
    _validate_against_existing(
        db,
        session=session,
        day_of_week=day_of_week,
        start_time=start_time,
        end_time=end_time,
        constraint_type=constraint_type,
        exclude_id=exclude_id,
    )


def get_course_session_time_constraint(
    db: Session,
    course_session_time_constraint_id: int,
) -> CourseSessionTimeConstraint:
    return require_by_id(
        db,
        CourseSessionTimeConstraint,
        course_session_time_constraint_id,
        "Course-session time constraint",
    )


def list_course_session_time_constraints(
    db: Session,
    pagination: PaginationParams,
    *,
    course_session_id: int | None = None,
) -> PaginatedResponse[CourseSessionTimeConstraintRead]:
    filters = []
    if course_session_id is not None:
        require_by_id(db, CourseSession, course_session_id, "Course session")
        filters.append(CourseSessionTimeConstraint.course_session_id == course_session_id)
    statement = (
        select(CourseSessionTimeConstraint)
        .where(*filters)
        .order_by(
            CourseSessionTimeConstraint.course_session_id,
            CourseSessionTimeConstraint.day_of_week.nulls_first(),
            CourseSessionTimeConstraint.start_time,
        )
    )
    count_statement = select(func.count()).select_from(CourseSessionTimeConstraint).where(*filters)
    rows, total = paginated_rows(db, statement, count_statement, pagination)
    return PaginatedResponse[CourseSessionTimeConstraintRead](
        items=[CourseSessionTimeConstraintRead.model_validate(row) for row in rows],
        total=total,
        page=pagination.page,
        page_size=pagination.page_size,
    )


def create_course_session_time_constraint(
    db: Session,
    payload: CourseSessionTimeConstraintCreate,
) -> CourseSessionTimeConstraint:
    session = require_editable_session(db, payload.course_session_id)
    _validate_constraint(
        db,
        session=session,
        day_of_week=payload.day_of_week,
        start_time=payload.start_time,
        end_time=payload.end_time,
        constraint_type=payload.constraint_type,
        preference_weight=payload.preference_weight,
    )
    constraint = CourseSessionTimeConstraint(**payload.model_dump())
    db.add(constraint)
    return commit_and_refresh(db, constraint)


def update_course_session_time_constraint(
    db: Session,
    course_session_time_constraint_id: int,
    payload: CourseSessionTimeConstraintUpdate,
) -> CourseSessionTimeConstraint:
    constraint = get_course_session_time_constraint(
        db,
        course_session_time_constraint_id,
    )
    session = require_editable_session(db, constraint.course_session_id)
    changes = validated_changes(
        payload,
        non_nullable_fields=(
            "course_session_id",
            "start_time",
            "end_time",
            "constraint_type",
        ),
    )
    course_session_id = changes.get(
        "course_session_id",
        constraint.course_session_id,
    )
    if course_session_id != constraint.course_session_id:
        session = require_editable_session(db, course_session_id)
    day_of_week = changes.get("day_of_week", constraint.day_of_week)
    start_time = changes.get("start_time", constraint.start_time)
    end_time = changes.get("end_time", constraint.end_time)
    constraint_type = changes.get(
        "constraint_type",
        constraint.constraint_type,
    )
    preference_weight = changes.get(
        "preference_weight",
        constraint.preference_weight,
    )
    _validate_constraint(
        db,
        session=session,
        day_of_week=day_of_week,
        start_time=start_time,
        end_time=end_time,
        constraint_type=constraint_type,
        preference_weight=preference_weight,
        exclude_id=constraint.id,
    )

    apply_changes(constraint, changes)
    return commit_and_refresh(db, constraint)


def delete_course_session_time_constraint(
    db: Session,
    course_session_time_constraint_id: int,
) -> MessageResponse:
    constraint = get_course_session_time_constraint(
        db,
        course_session_time_constraint_id,
    )
    require_editable_session(db, constraint.course_session_id)
    commit_delete(db, constraint)
    return MessageResponse(message="Course-session time constraint deleted.")
