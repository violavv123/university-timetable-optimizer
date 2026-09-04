from collections import defaultdict

from app.core.exceptions import BusinessRuleError, InvalidReferenceError
from app.models.course_session import CourseSession
from app.models.course_session_dependency import CourseSessionDependency
from app.models.enums import DependencyType
from app.schemas.common import MessageResponse, PaginatedResponse, PaginationParams
from app.schemas.course_session_dependency import (
    CourseSessionDependencyCreate,
    CourseSessionDependencyRead,
    CourseSessionDependencyUpdate,
)
from app.services.common import (
    apply_changes,
    commit_and_refresh,
    commit_delete,
    ensure_unique,
    paginated_rows,
    require_by_id,
    validated_changes,
)
from app.services.scheduling_input.guards import require_editable_session
from sqlalchemy import func, select
from sqlalchemy.orm import Session


def _validate_gap_configuration(
    *,
    dependency_type: DependencyType,
    min_gap_slots: int | None,
    max_gap_slots: int | None,
) -> None:
    if min_gap_slots is not None and min_gap_slots < 0:
        raise BusinessRuleError("min_gap_slots cannot be negative.")
    if max_gap_slots is not None and max_gap_slots < 0:
        raise BusinessRuleError("max_gap_slots cannot be negative.")
    if min_gap_slots is not None and max_gap_slots is not None and max_gap_slots < min_gap_slots:
        raise BusinessRuleError("max_gap_slots cannot be smaller than min_gap_slots.")

    if dependency_type in {
        DependencyType.SAME_DAY,
        DependencyType.DIFFERENT_DAY,
    } and (min_gap_slots is not None or max_gap_slots is not None):
        raise BusinessRuleError("SAME_DAY and DIFFERENT_DAY dependencies cannot define slot gaps.")
    if dependency_type == DependencyType.CONSECUTIVE:
        invalid_min = min_gap_slots not in {None, 0}
        invalid_max = max_gap_slots not in {None, 0}
        if invalid_min or invalid_max:
            raise BusinessRuleError(
                "CONSECUTIVE requires a zero gap; omit both gap fields or use zero."
            )


def _ensure_compatible_sessions(
    predecessor: CourseSession,
    successor: CourseSession,
) -> None:
    if predecessor.id == successor.id:
        raise BusinessRuleError("A course session cannot depend on itself.")
    predecessor_offering = predecessor.course_offering
    successor_offering = successor.course_offering
    if predecessor_offering.academic_term_id != successor_offering.academic_term_id:
        raise InvalidReferenceError(
            "Dependent sessions must belong to the same academic term.",
            details={
                "predecessor_session_id": predecessor.id,
                "predecessor_academic_term_id": (predecessor_offering.academic_term_id),
                "successor_session_id": successor.id,
                "successor_academic_term_id": successor_offering.academic_term_id,
            },
        )


def _ensure_no_contradictory_pair(
    db: Session,
    *,
    predecessor_session_id: int,
    successor_session_id: int,
    dependency_type: DependencyType,
    exclude_id: int | None = None,
) -> None:
    statement = select(CourseSessionDependency).where(
        CourseSessionDependency.predecessor_session_id == predecessor_session_id,
        CourseSessionDependency.successor_session_id == successor_session_id,
    )
    if exclude_id is not None:
        statement = statement.where(CourseSessionDependency.id != exclude_id)
    for existing in db.scalars(statement).all():
        same_day_conflict = {
            existing.dependency_type,
            dependency_type,
        } == {DependencyType.SAME_DAY, DependencyType.DIFFERENT_DAY}
        consecutive_redundancy = (
            existing.dependency_type == DependencyType.CONSECUTIVE
            or dependency_type == DependencyType.CONSECUTIVE
        )
        if same_day_conflict or consecutive_redundancy:
            raise BusinessRuleError(
                "The requested dependency conflicts with an existing dependency.",
                details={
                    "existing_dependency_id": existing.id,
                    "existing_dependency_type": existing.dependency_type,
                    "requested_dependency_type": dependency_type,
                },
            )


def _ensure_acyclic(
    db: Session,
    *,
    predecessor_session_id: int,
    successor_session_id: int,
    exclude_id: int | None = None,
) -> None:
    statement = select(
        CourseSessionDependency.predecessor_session_id,
        CourseSessionDependency.successor_session_id,
    )
    if exclude_id is not None:
        statement = statement.where(CourseSessionDependency.id != exclude_id)
    adjacency: defaultdict[int, set[int]] = defaultdict(set)
    for predecessor_id, successor_id in db.execute(statement).tuples().all():
        adjacency[predecessor_id].add(successor_id)
    adjacency[predecessor_session_id].add(successor_session_id)

    stack = [successor_session_id]
    visited: set[int] = set()
    while stack:
        current_id = stack.pop()
        if current_id == predecessor_session_id:
            raise BusinessRuleError(
                "Course-session dependencies cannot contain an indirect cycle.",
                details={
                    "predecessor_session_id": predecessor_session_id,
                    "successor_session_id": successor_session_id,
                },
            )
        if current_id in visited:
            continue
        visited.add(current_id)
        stack.extend(adjacency[current_id])


def _validate_dependency(
    db: Session,
    *,
    predecessor_session_id: int,
    successor_session_id: int,
    dependency_type: DependencyType,
    min_gap_slots: int | None,
    max_gap_slots: int | None,
    exclude_id: int | None = None,
) -> None:
    predecessor = require_editable_session(db, predecessor_session_id)
    successor = require_editable_session(db, successor_session_id)
    _ensure_compatible_sessions(predecessor, successor)
    _validate_gap_configuration(
        dependency_type=dependency_type,
        min_gap_slots=min_gap_slots,
        max_gap_slots=max_gap_slots,
    )
    _ensure_no_contradictory_pair(
        db,
        predecessor_session_id=predecessor_session_id,
        successor_session_id=successor_session_id,
        dependency_type=dependency_type,
        exclude_id=exclude_id,
    )
    _ensure_acyclic(
        db,
        predecessor_session_id=predecessor_session_id,
        successor_session_id=successor_session_id,
        exclude_id=exclude_id,
    )


def get_course_session_dependency(
    db: Session,
    course_session_dependency_id: int,
) -> CourseSessionDependency:
    return require_by_id(
        db,
        CourseSessionDependency,
        course_session_dependency_id,
        "Course-session dependency",
    )


def list_course_session_dependencies(
    db: Session,
    pagination: PaginationParams,
    *,
    course_session_id: int | None = None,
) -> PaginatedResponse[CourseSessionDependencyRead]:
    filters = []
    if course_session_id is not None:
        require_by_id(db, CourseSession, course_session_id, "Course session")
        filters.append(
            (CourseSessionDependency.predecessor_session_id == course_session_id)
            | (CourseSessionDependency.successor_session_id == course_session_id)
        )
    statement = (
        select(CourseSessionDependency)
        .where(*filters)
        .order_by(
            CourseSessionDependency.predecessor_session_id,
            CourseSessionDependency.successor_session_id,
            CourseSessionDependency.dependency_type,
        )
    )
    count_statement = select(func.count()).select_from(CourseSessionDependency).where(*filters)
    rows, total = paginated_rows(db, statement, count_statement, pagination)
    return PaginatedResponse[CourseSessionDependencyRead](
        items=[CourseSessionDependencyRead.model_validate(row) for row in rows],
        total=total,
        page=pagination.page,
        page_size=pagination.page_size,
    )


def create_course_session_dependency(
    db: Session,
    payload: CourseSessionDependencyCreate,
) -> CourseSessionDependency:
    _validate_dependency(
        db,
        predecessor_session_id=payload.predecessor_session_id,
        successor_session_id=payload.successor_session_id,
        dependency_type=payload.dependency_type,
        min_gap_slots=payload.min_gap_slots,
        max_gap_slots=payload.max_gap_slots,
    )
    ensure_unique(
        db,
        CourseSessionDependency,
        "Course-session dependency",
        [
            "predecessor_session_id",
            "successor_session_id",
            "dependency_type",
        ],
        CourseSessionDependency.predecessor_session_id == payload.predecessor_session_id,
        CourseSessionDependency.successor_session_id == payload.successor_session_id,
        CourseSessionDependency.dependency_type == payload.dependency_type,
    )
    dependency = CourseSessionDependency(**payload.model_dump())
    db.add(dependency)
    return commit_and_refresh(db, dependency)


def update_course_session_dependency(
    db: Session,
    course_session_dependency_id: int,
    payload: CourseSessionDependencyUpdate,
) -> CourseSessionDependency:
    dependency = get_course_session_dependency(
        db,
        course_session_dependency_id,
    )
    changes = validated_changes(
        payload,
        non_nullable_fields=(
            "predecessor_session_id",
            "successor_session_id",
            "dependency_type",
        ),
    )
    predecessor_session_id = changes.get(
        "predecessor_session_id",
        dependency.predecessor_session_id,
    )
    successor_session_id = changes.get(
        "successor_session_id",
        dependency.successor_session_id,
    )
    dependency_type = changes.get(
        "dependency_type",
        dependency.dependency_type,
    )
    min_gap_slots = changes.get("min_gap_slots", dependency.min_gap_slots)
    max_gap_slots = changes.get("max_gap_slots", dependency.max_gap_slots)
    _validate_dependency(
        db,
        predecessor_session_id=predecessor_session_id,
        successor_session_id=successor_session_id,
        dependency_type=dependency_type,
        min_gap_slots=min_gap_slots,
        max_gap_slots=max_gap_slots,
        exclude_id=dependency.id,
    )
    ensure_unique(
        db,
        CourseSessionDependency,
        "Course-session dependency",
        [
            "predecessor_session_id",
            "successor_session_id",
            "dependency_type",
        ],
        CourseSessionDependency.predecessor_session_id == predecessor_session_id,
        CourseSessionDependency.successor_session_id == successor_session_id,
        CourseSessionDependency.dependency_type == dependency_type,
        exclude_id=dependency.id,
    )

    apply_changes(dependency, changes)
    return commit_and_refresh(db, dependency)


def delete_course_session_dependency(
    db: Session,
    course_session_dependency_id: int,
) -> MessageResponse:
    dependency = get_course_session_dependency(
        db,
        course_session_dependency_id,
    )
    require_editable_session(db, dependency.predecessor_session_id)
    require_editable_session(db, dependency.successor_session_id)
    commit_delete(db, dependency)
    return MessageResponse(message="Course-session dependency deleted.")
