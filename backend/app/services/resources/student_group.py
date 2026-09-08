from collections import defaultdict
from dataclasses import dataclass
from math import ceil

from app.core.exceptions import (
    BusinessRuleError,
    InvalidReferenceError,
    ResourceInUseError,
)
from app.models.academic_term import AcademicTerm
from app.models.course_offering import CourseOffering
from app.models.course_session import CourseSession
from app.models.course_session_group import CourseSessionGroup
from app.models.enums import (
    CourseOfferingStatus,
    StudentGroupType,
    TermType,
)
from app.models.program_semester import ProgramSemester
from app.models.room import Room
from app.models.scheduling_profile import SchedulingProfile
from app.models.student_group import StudentGroup
from app.models.timetable_entry import TimetableEntry
from app.models.timetable_run import TimetableRun
from app.schemas.common import MessageResponse, PaginatedResponse, PaginationParams
from app.schemas.student_group import (
    StudentGroupCreate,
    StudentGroupHierarchySyncRequest,
    StudentGroupRead,
    StudentGroupUpdate,
)
from app.services.academic.hierarchy import (
    require_active_program_semester_hierarchy,
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
from sqlalchemy import func, or_, select
from sqlalchemy.orm import Session

ALLOWED_PARENT_TYPES: dict[StudentGroupType, set[StudentGroupType]] = {
    StudentGroupType.COHORT: set(),
    StudentGroupType.LECTURE_GROUP: {StudentGroupType.COHORT},
    StudentGroupType.NUMERICAL_GROUP: {StudentGroupType.COHORT},
    StudentGroupType.LAB_GROUP: {
        StudentGroupType.COHORT,
        StudentGroupType.LECTURE_GROUP,
        StudentGroupType.NUMERICAL_GROUP,
    },
}


@dataclass(frozen=True, slots=True)
class StudentGroupPlanRow:
    name: str
    group_type: StudentGroupType
    student_count: int
    parent_name: str | None


def _balanced_sizes(total: int, maximum: int) -> tuple[int, ...]:
    group_count = ceil(total / maximum)
    base, remainder = divmod(total, group_count)
    return tuple(base + (index < remainder) for index in range(group_count))


def build_student_group_hierarchy_plan(
    *,
    cohort_name: str,
    student_count: int,
    max_lecture_students: int,
    max_numerical_students: int,
    max_lab_students: int,
) -> tuple[StudentGroupPlanRow, ...]:
    rows = [
        StudentGroupPlanRow(
            cohort_name,
            StudentGroupType.COHORT,
            student_count,
            None,
        )
    ]
    for lecture_number, lecture_size in enumerate(
        _balanced_sizes(student_count, max_lecture_students),
        start=1,
    ):
        lecture_name = f"{cohort_name}-G{lecture_number}"
        rows.append(
            StudentGroupPlanRow(
                lecture_name,
                StudentGroupType.LECTURE_GROUP,
                lecture_size,
                cohort_name,
            )
        )
        for numerical_number, numerical_size in enumerate(
            _balanced_sizes(lecture_size, max_numerical_students),
            start=1,
        ):
            numerical_name = f"{lecture_name}-N{numerical_number}"
            rows.append(
                StudentGroupPlanRow(
                    numerical_name,
                    StudentGroupType.NUMERICAL_GROUP,
                    numerical_size,
                    lecture_name,
                )
            )
            for lab_number, lab_size in enumerate(
                _balanced_sizes(numerical_size, max_lab_students),
                start=1,
            ):
                rows.append(
                    StudentGroupPlanRow(
                        f"{numerical_name}-L{lab_number}",
                        StudentGroupType.LAB_GROUP,
                        lab_size,
                        numerical_name,
                    )
                )
    return tuple(rows)


def synchronize_student_group_hierarchy(
    db: Session,
    payload: StudentGroupHierarchySyncRequest,
) -> tuple[StudentGroup, ...]:
    """Idempotently synchronize a standard cohort/lecture/numerical/lab tree.

    Existing linked groups are never structurally rewritten. This keeps saved
    and published timetables reproducible when enrollment changes arrive late.
    """

    cohort_name = " ".join(payload.cohort_name.split())
    program_semester = require_by_id(
        db,
        ProgramSemester,
        payload.program_semester_id,
        "Program semester",
    )
    academic_term = require_by_id(
        db,
        AcademicTerm,
        payload.academic_term_id,
        "Academic term",
    )
    profile = require_by_id(
        db,
        SchedulingProfile,
        payload.scheduling_profile_id,
        "Scheduling profile",
    )
    require_active_program_semester_hierarchy(program_semester)
    require_active(academic_term, "Academic term")
    require_active(profile, "Scheduling profile")
    _validate_semester_term(program_semester, academic_term)
    if program_semester.study_program.faculty_id != profile.faculty_id:
        raise InvalidReferenceError(
            "The scheduling profile and program semester must belong to the same faculty.",
            details={
                "program_semester_id": program_semester.id,
                "scheduling_profile_id": profile.id,
            },
        )

    plan = build_student_group_hierarchy_plan(
        cohort_name=cohort_name,
        student_count=payload.student_count,
        max_lecture_students=profile.max_lecture_students,
        max_numerical_students=profile.max_numerical_students,
        max_lab_students=profile.max_lab_students,
    )
    managed_prefix = f"{cohort_name}-G"
    existing = tuple(
        db.scalars(
            select(StudentGroup).where(
                StudentGroup.program_semester_id == program_semester.id,
                StudentGroup.academic_term_id == academic_term.id,
                or_(
                    func.lower(StudentGroup.name) == cohort_name.lower(),
                    StudentGroup.name.startswith(managed_prefix),
                ),
            )
        ).all()
    )
    existing_by_name = {group.name.lower(): group for group in existing}
    plan_names = {row.name.lower() for row in plan}
    plan_by_name = {row.name.lower(): row for row in plan}
    changed_ids: set[int] = set()
    for group in existing:
        row = plan_by_name.get(group.name.lower())
        if row is None or not group.is_active:
            changed_ids.add(group.id)
            continue
        expected_parent = (
            None if row.parent_name is None else existing_by_name.get(row.parent_name.lower())
        )
        expected_parent_id = None if expected_parent is None else expected_parent.id
        if (
            row.group_type != group.group_type
            or row.student_count != group.student_count
            or group.parent_group_id != expected_parent_id
        ):
            changed_ids.add(group.id)
    linked_changed_id = (
        db.scalar(
            select(CourseSessionGroup.student_group_id)
            .where(CourseSessionGroup.student_group_id.in_(changed_ids))
            .limit(1)
        )
        if changed_ids
        else None
    )
    if linked_changed_id is not None:
        raise ResourceInUseError(
            "A linked student-group hierarchy cannot be structurally synchronized.",
            details={"student_group_id": linked_changed_id},
        )

    resolved_by_name: dict[str, StudentGroup] = {}
    for row in plan:
        key = row.name.lower()
        parent = None if row.parent_name is None else resolved_by_name[row.parent_name.lower()]
        resolved_group = existing_by_name.get(key)
        if resolved_group is None:
            resolved_group = StudentGroup(
                program_semester_id=program_semester.id,
                academic_term_id=academic_term.id,
                parent_group_id=None if parent is None else parent.id,
                name=row.name,
                group_type=row.group_type,
                student_count=row.student_count,
                is_active=True,
            )
            db.add(resolved_group)
            db.flush()
        else:
            resolved_group.parent_group_id = None if parent is None else parent.id
            resolved_group.group_type = row.group_type
            resolved_group.student_count = row.student_count
            resolved_group.is_active = True
        resolved_by_name[key] = resolved_group

    for group in existing:
        if group.name.lower() not in plan_names:
            group.is_active = False
    db.commit()
    result = tuple(resolved_by_name[row.name.lower()] for row in plan)
    for group in result:
        db.refresh(group)
    return result


def _validate_semester_term(
    program_semester: ProgramSemester,
    academic_term: AcademicTerm,
) -> None:
    expected_term_type = (
        TermType.WINTER if program_semester.semester_number % 2 == 1 else TermType.SUMMER
    )
    if academic_term.term_type != expected_term_type:
        raise InvalidReferenceError(
            "The academic term type is incompatible with the program semester.",
            details={
                "program_semester_id": program_semester.id,
                "semester_number": program_semester.semester_number,
                "expected_term_type": expected_term_type,
                "academic_term_id": academic_term.id,
                "actual_term_type": academic_term.term_type,
            },
        )


def _walk_active_parent_chain(
    db: Session,
    parent: StudentGroup,
    *,
    group_id: int | None,
    require_active_parents: bool,
) -> None:
    visited: set[int] = set()
    current: StudentGroup | None = parent
    while current is not None:
        if current.id == group_id:
            raise BusinessRuleError(
                "Student-group parent relationships cannot contain a cycle.",
                details={"student_group_id": group_id},
            )
        if current.id in visited:
            raise BusinessRuleError(
                "The existing student-group hierarchy already contains a cycle.",
                details={"student_group_id": current.id},
            )
        visited.add(current.id)
        if require_active_parents:
            require_active(current, "Parent student group")
        current = (
            None
            if current.parent_group_id is None
            else require_by_id(
                db,
                StudentGroup,
                current.parent_group_id,
                "Parent student group",
            )
        )


def _validate_parent(
    db: Session,
    *,
    group_id: int | None,
    program_semester_id: int,
    academic_term_id: int,
    parent_group_id: int | None,
    group_type: StudentGroupType,
    student_count: int,
    final_is_active: bool,
) -> None:
    if group_type == StudentGroupType.COHORT:
        if parent_group_id is not None:
            raise BusinessRuleError("A cohort cannot have a parent group.")
        return
    if parent_group_id is None:
        raise BusinessRuleError("Lecture, numerical, and laboratory groups require a parent group.")

    parent = require_by_id(
        db,
        StudentGroup,
        parent_group_id,
        "Parent student group",
    )
    if parent.id == group_id:
        raise BusinessRuleError("A student group cannot be its own parent.")
    if (
        parent.program_semester_id != program_semester_id
        or parent.academic_term_id != academic_term_id
    ):
        raise InvalidReferenceError(
            "Parent and child groups must belong to the same semester and term.",
            details={
                "parent_group_id": parent.id,
                "parent_program_semester_id": parent.program_semester_id,
                "parent_academic_term_id": parent.academic_term_id,
                "program_semester_id": program_semester_id,
                "academic_term_id": academic_term_id,
            },
        )
    if parent.group_type not in ALLOWED_PARENT_TYPES[group_type]:
        raise BusinessRuleError(
            "The selected parent type is not broader than the child group type.",
            details={
                "parent_group_id": parent.id,
                "parent_group_type": parent.group_type,
                "child_group_type": group_type,
            },
        )
    if student_count > parent.student_count:
        raise BusinessRuleError(
            "A child group cannot contain more students than its parent.",
            details={
                "parent_group_id": parent.id,
                "parent_student_count": parent.student_count,
                "child_student_count": student_count,
            },
        )
    _walk_active_parent_chain(
        db,
        parent,
        group_id=group_id,
        require_active_parents=final_is_active,
    )


def _validate_child_capacity(
    db: Session,
    *,
    group_id: int,
    student_count: int,
    final_is_active: bool,
    program_semester_id: int,
    academic_term_id: int,
    group_type: StudentGroupType,
) -> None:
    children = list(
        db.scalars(
            select(StudentGroup).where(
                StudentGroup.parent_group_id == group_id,
                StudentGroup.is_active.is_(True),
            )
        ).all()
    )
    if children and not final_is_active:
        raise ResourceInUseError(
            "A student group with active child groups cannot be deactivated.",
            details={
                "student_group_id": group_id,
                "child_group_id": children[0].id,
            },
        )

    totals_by_type: defaultdict[StudentGroupType, int] = defaultdict(int)
    for child in children:
        if (
            child.program_semester_id != program_semester_id
            or child.academic_term_id != academic_term_id
        ):
            raise BusinessRuleError(
                "Changing this group would separate it from an existing child.",
                details={
                    "student_group_id": group_id,
                    "child_group_id": child.id,
                },
            )
        if group_type not in ALLOWED_PARENT_TYPES[child.group_type]:
            raise BusinessRuleError(
                "Changing group_type would invalidate an existing child hierarchy.",
                details={
                    "student_group_id": group_id,
                    "child_group_id": child.id,
                },
            )
        if child.student_count > student_count:
            raise BusinessRuleError(
                "student_count cannot be smaller than an active child group.",
                details={
                    "student_group_id": group_id,
                    "child_group_id": child.id,
                    "child_student_count": child.student_count,
                },
            )
        totals_by_type[child.group_type] += child.student_count

    for child_type, total in totals_by_type.items():
        if total > student_count:
            raise BusinessRuleError(
                "Active sibling groups of the same type exceed their parent's size.",
                details={
                    "student_group_id": group_id,
                    "child_group_type": child_type,
                    "children_student_count": total,
                    "parent_student_count": student_count,
                },
            )


def _validate_sibling_capacity(
    db: Session,
    *,
    group_id: int | None,
    parent_group_id: int | None,
    group_type: StudentGroupType,
    student_count: int,
    final_is_active: bool,
) -> None:
    if parent_group_id is None or not final_is_active:
        return
    parent = require_by_id(
        db,
        StudentGroup,
        parent_group_id,
        "Parent student group",
    )
    statement = select(func.coalesce(func.sum(StudentGroup.student_count), 0)).where(
        StudentGroup.parent_group_id == parent_group_id,
        StudentGroup.group_type == group_type,
        StudentGroup.is_active.is_(True),
    )
    if group_id is not None:
        statement = statement.where(StudentGroup.id != group_id)
    siblings_total = int(db.scalar(statement) or 0)
    if siblings_total + student_count > parent.student_count:
        raise BusinessRuleError(
            "Active sibling groups of the same type cannot exceed their parent's size.",
            details={
                "parent_group_id": parent.id,
                "parent_student_count": parent.student_count,
                "requested_children_student_count": siblings_total + student_count,
            },
        )


def _attached_open_session_id(db: Session, student_group_id: int) -> int | None:
    return db.scalar(
        select(CourseSession.id)
        .join(
            CourseSessionGroup,
            CourseSessionGroup.course_session_id == CourseSession.id,
        )
        .join(
            CourseOffering,
            CourseOffering.id == CourseSession.course_offering_id,
        )
        .where(
            CourseSessionGroup.student_group_id == student_group_id,
            CourseSession.is_active.is_(True),
            CourseOffering.status.in_([CourseOfferingStatus.DRAFT, CourseOfferingStatus.READY]),
        )
        .limit(1)
    )


def _validate_assigned_room_capacity(
    db: Session,
    *,
    group_id: int,
    student_count: int,
    final_is_active: bool,
) -> None:
    if not final_is_active:
        return

    assignments: set[tuple[int, int]] = set()
    exact_room_statement = (
        select(CourseSession.id, CourseSession.required_room_id)
        .join(
            CourseSessionGroup,
            CourseSessionGroup.course_session_id == CourseSession.id,
        )
        .join(
            CourseOffering,
            CourseOffering.id == CourseSession.course_offering_id,
        )
        .where(
            CourseSessionGroup.student_group_id == group_id,
            CourseSession.required_room_id.is_not(None),
            CourseSession.is_active.is_(True),
            CourseOffering.status.in_([CourseOfferingStatus.DRAFT, CourseOfferingStatus.READY]),
        )
    )
    assignments.update(
        (session_id, room_id)
        for session_id, room_id in db.execute(exact_room_statement).tuples().all()
        if room_id is not None
    )
    published_statement = (
        select(TimetableEntry.course_session_id, TimetableEntry.room_id)
        .join(
            TimetableRun,
            TimetableRun.id == TimetableEntry.timetable_run_id,
        )
        .join(
            CourseSessionGroup,
            CourseSessionGroup.course_session_id == TimetableEntry.course_session_id,
        )
        .where(
            CourseSessionGroup.student_group_id == group_id,
            TimetableRun.is_published.is_(True),
        )
    )
    assignments.update(db.execute(published_statement).tuples().all())

    for course_session_id, room_id in assignments:
        other_students = int(
            db.scalar(
                select(func.coalesce(func.sum(StudentGroup.student_count), 0))
                .select_from(CourseSessionGroup)
                .join(
                    StudentGroup,
                    StudentGroup.id == CourseSessionGroup.student_group_id,
                )
                .where(
                    CourseSessionGroup.course_session_id == course_session_id,
                    CourseSessionGroup.student_group_id != group_id,
                    StudentGroup.is_active.is_(True),
                )
            )
            or 0
        )
        room = require_by_id(db, Room, room_id, "Room")
        required_capacity = other_students + student_count
        if required_capacity > room.capacity:
            raise BusinessRuleError(
                "student_count would exceed an assigned room's capacity.",
                details={
                    "student_group_id": group_id,
                    "course_session_id": course_session_id,
                    "room_id": room.id,
                    "required_capacity": required_capacity,
                    "room_capacity": room.capacity,
                },
            )


def _validate_configuration(
    db: Session,
    *,
    group_id: int | None,
    program_semester_id: int,
    academic_term_id: int,
    parent_group_id: int | None,
    group_type: StudentGroupType,
    student_count: int,
    final_is_active: bool,
) -> None:
    if student_count <= 0:
        raise BusinessRuleError("student_count must be greater than zero.")
    program_semester = require_by_id(
        db,
        ProgramSemester,
        program_semester_id,
        "Program semester",
    )
    academic_term = require_by_id(
        db,
        AcademicTerm,
        academic_term_id,
        "Academic term",
    )
    _validate_semester_term(program_semester, academic_term)
    if final_is_active:
        require_active_program_semester_hierarchy(program_semester)
        require_active(academic_term, "Academic term")

    _validate_parent(
        db,
        group_id=group_id,
        program_semester_id=program_semester_id,
        academic_term_id=academic_term_id,
        parent_group_id=parent_group_id,
        group_type=group_type,
        student_count=student_count,
        final_is_active=final_is_active,
    )
    _validate_sibling_capacity(
        db,
        group_id=group_id,
        parent_group_id=parent_group_id,
        group_type=group_type,
        student_count=student_count,
        final_is_active=final_is_active,
    )


def get_student_group(db: Session, student_group_id: int) -> StudentGroup:
    return require_by_id(db, StudentGroup, student_group_id, "Student group")


def list_student_groups(
    db: Session,
    pagination: PaginationParams,
    *,
    program_semester_id: int | None = None,
    academic_term_id: int | None = None,
    parent_group_id: int | None = None,
    include_inactive: bool = False,
) -> PaginatedResponse[StudentGroupRead]:
    filters = []
    if program_semester_id is not None:
        require_by_id(db, ProgramSemester, program_semester_id, "Program semester")
        filters.append(StudentGroup.program_semester_id == program_semester_id)
    if academic_term_id is not None:
        require_by_id(db, AcademicTerm, academic_term_id, "Academic term")
        filters.append(StudentGroup.academic_term_id == academic_term_id)
    if parent_group_id is not None:
        require_by_id(db, StudentGroup, parent_group_id, "Parent student group")
        filters.append(StudentGroup.parent_group_id == parent_group_id)
    if not include_inactive:
        filters.append(StudentGroup.is_active.is_(True))

    statement = (
        select(StudentGroup)
        .where(*filters)
        .order_by(
            StudentGroup.program_semester_id,
            StudentGroup.academic_term_id,
            StudentGroup.parent_group_id.nulls_first(),
            StudentGroup.name,
        )
    )
    count_statement = select(func.count()).select_from(StudentGroup).where(*filters)
    rows, total = paginated_rows(db, statement, count_statement, pagination)
    return PaginatedResponse[StudentGroupRead](
        items=[StudentGroupRead.model_validate(row) for row in rows],
        total=total,
        page=pagination.page,
        page_size=pagination.page_size,
    )


def create_student_group(
    db: Session,
    payload: StudentGroupCreate,
) -> StudentGroup:
    name = " ".join(payload.name.split())
    if not name:
        raise BusinessRuleError("name cannot be blank.")
    _validate_configuration(
        db,
        group_id=None,
        program_semester_id=payload.program_semester_id,
        academic_term_id=payload.academic_term_id,
        parent_group_id=payload.parent_group_id,
        group_type=payload.group_type,
        student_count=payload.student_count,
        final_is_active=payload.is_active,
    )
    ensure_unique(
        db,
        StudentGroup,
        "Student group",
        ["program_semester_id", "academic_term_id", "name"],
        StudentGroup.program_semester_id == payload.program_semester_id,
        StudentGroup.academic_term_id == payload.academic_term_id,
        func.lower(StudentGroup.name) == name.lower(),
    )
    values = payload.model_dump()
    values["name"] = name
    student_group = StudentGroup(**values)
    db.add(student_group)
    return commit_and_refresh(db, student_group)


def update_student_group(
    db: Session,
    student_group_id: int,
    payload: StudentGroupUpdate,
) -> StudentGroup:
    student_group = get_student_group(db, student_group_id)
    changes = validated_changes(
        payload,
        non_nullable_fields=(
            "program_semester_id",
            "academic_term_id",
            "name",
            "group_type",
            "student_count",
            "is_active",
        ),
    )
    program_semester_id = changes.get(
        "program_semester_id",
        student_group.program_semester_id,
    )
    academic_term_id = changes.get(
        "academic_term_id",
        student_group.academic_term_id,
    )
    parent_group_id = changes.get(
        "parent_group_id",
        student_group.parent_group_id,
    )
    group_type = changes.get("group_type", student_group.group_type)
    student_count = changes.get("student_count", student_group.student_count)
    final_is_active = changes.get("is_active", student_group.is_active)
    if "name" in changes:
        changes["name"] = " ".join(changes["name"].split())
        if not changes["name"]:
            raise BusinessRuleError("name cannot be blank.")
    name = changes.get("name", student_group.name)

    attached_session_id = _attached_open_session_id(db, student_group.id)
    structural_fields = {
        "program_semester_id",
        "academic_term_id",
        "group_type",
    }
    if attached_session_id is not None and structural_fields.intersection(changes):
        raise ResourceInUseError(
            "A group attached to an open session cannot change semester, term, or type.",
            details={
                "student_group_id": student_group.id,
                "course_session_id": attached_session_id,
            },
        )
    if attached_session_id is not None and not final_is_active:
        raise ResourceInUseError(
            "A group attached to an open session cannot be deactivated.",
            details={
                "student_group_id": student_group.id,
                "course_session_id": attached_session_id,
            },
        )

    _validate_configuration(
        db,
        group_id=student_group.id,
        program_semester_id=program_semester_id,
        academic_term_id=academic_term_id,
        parent_group_id=parent_group_id,
        group_type=group_type,
        student_count=student_count,
        final_is_active=final_is_active,
    )
    _validate_child_capacity(
        db,
        group_id=student_group.id,
        student_count=student_count,
        final_is_active=final_is_active,
        program_semester_id=program_semester_id,
        academic_term_id=academic_term_id,
        group_type=group_type,
    )
    _validate_assigned_room_capacity(
        db,
        group_id=student_group.id,
        student_count=student_count,
        final_is_active=final_is_active,
    )
    ensure_unique(
        db,
        StudentGroup,
        "Student group",
        ["program_semester_id", "academic_term_id", "name"],
        StudentGroup.program_semester_id == program_semester_id,
        StudentGroup.academic_term_id == academic_term_id,
        func.lower(StudentGroup.name) == name.lower(),
        exclude_id=student_group.id,
    )

    apply_changes(student_group, changes)
    return commit_and_refresh(db, student_group)


def delete_student_group(
    db: Session,
    student_group_id: int,
) -> MessageResponse:
    student_group = get_student_group(db, student_group_id)
    attached_session_id = _attached_open_session_id(db, student_group.id)
    if attached_session_id is not None:
        raise ResourceInUseError(
            "A group attached to an open session cannot be deactivated.",
            details={
                "student_group_id": student_group.id,
                "course_session_id": attached_session_id,
            },
        )
    _validate_child_capacity(
        db,
        group_id=student_group.id,
        student_count=student_group.student_count,
        final_is_active=False,
        program_semester_id=student_group.program_semester_id,
        academic_term_id=student_group.academic_term_id,
        group_type=student_group.group_type,
    )
    student_group.is_active = False
    commit_and_refresh(db, student_group)
    return MessageResponse(message="Student group deactivated successfully.")
