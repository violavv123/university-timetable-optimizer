from dataclasses import dataclass
from datetime import time
from typing import Any, cast

from app.models.course_offering import CourseOffering
from app.models.course_session import CourseSession
from app.models.course_session_dependency import CourseSessionDependency
from app.models.course_session_group import CourseSessionGroup
from app.models.course_session_staff import CourseSessionStaff
from app.models.course_session_time_constraint import (
    CourseSessionTimeConstraint,
)
from app.models.curriculum_course import CurriculumCourse
from app.models.enums import (
    AvailabilityType,
    ComponentType,
    CourseOfferingStatus,
    DependencyType,
    RoomStatus,
    RoomType,
    TeachingRole,
    TimeConstraintType,
)
from app.models.program_semester import ProgramSemester
from app.models.room import Room
from app.models.room_availability import RoomAvailability
from app.models.scheduling_profile import SchedulingProfile
from app.models.staff_availability import StaffAvailability
from app.models.staff_course import StaffCourse
from app.models.staff_member import StaffMember
from app.models.student_group import StudentGroup
from app.models.study_program import StudyProgram
from app.models.time_slot import TimeSlot
from app.models.timetable_entry import TimetableEntry
from app.models.timetable_run import TimetableRun
from app.services.common import require_by_id
from app.services.timetable.types import (
    TimetableConflict,
    TimetableValidationResult,
)
from sqlalchemy import func, select
from sqlalchemy.orm import InstrumentedAttribute, Session


@dataclass(slots=True)
class _ResolvedAssignment:
    run: TimetableRun
    session: CourseSession
    room: Room
    start_slot: TimeSlot
    slots: tuple[TimeSlot, ...]
    end_time: time
    staff_ids: frozenset[int]
    group_ids: frozenset[int]
    student_count: int


def _append_conflict(
    conflicts: list[TimetableConflict],
    code: str,
    message: str,
    **details: Any,
) -> None:
    conflict = TimetableConflict(code=code, message=message, details=details)
    fingerprint = (code, repr(sorted(details.items())))
    existing = {(item.code, repr(sorted(item.details.items()))) for item in conflicts}
    if fingerprint not in existing:
        conflicts.append(conflict)


def _session_student_count(db: Session, course_session_id: int) -> int:
    return int(
        db.scalar(
            select(func.coalesce(func.sum(StudentGroup.student_count), 0))
            .select_from(CourseSessionGroup)
            .join(
                StudentGroup,
                StudentGroup.id == CourseSessionGroup.student_group_id,
            )
            .where(CourseSessionGroup.course_session_id == course_session_id)
        )
        or 0
    )


def _component_capacity(profile: SchedulingProfile, session: CourseSession) -> int:
    if session.component_type == ComponentType.LECTURE:
        return profile.max_lecture_students
    if session.component_type == ComponentType.NUMERICAL:
        return profile.max_numerical_students
    return profile.max_lab_students


def _resolve_slots(
    db: Session,
    *,
    run: TimetableRun,
    session: CourseSession,
    start_slot: TimeSlot,
    conflicts: list[TimetableConflict],
    entry_id: int | None,
) -> tuple[TimeSlot, ...]:
    if start_slot.scheduling_profile_id != run.scheduling_profile_id:
        _append_conflict(
            conflicts,
            "START_SLOT_PROFILE_MISMATCH",
            "The start slot does not belong to the run's scheduling profile.",
            entry_id=entry_id,
            start_slot_id=start_slot.id,
            expected_profile_id=run.scheduling_profile_id,
            actual_profile_id=start_slot.scheduling_profile_id,
        )
        return ()

    expected_indices = list(
        range(
            start_slot.slot_index,
            start_slot.slot_index + session.duration_slots,
        )
    )
    slots = tuple(
        db.scalars(
            select(TimeSlot)
            .where(
                TimeSlot.scheduling_profile_id == run.scheduling_profile_id,
                TimeSlot.day_of_week == start_slot.day_of_week,
                TimeSlot.slot_index.in_(expected_indices),
            )
            .order_by(TimeSlot.slot_index)
        ).all()
    )
    actual_indices = [slot.slot_index for slot in slots]
    if actual_indices != expected_indices or any(not slot.is_active for slot in slots):
        _append_conflict(
            conflicts,
            "NON_CONSECUTIVE_SLOTS",
            "Session duration must fit consecutive active slots on one day.",
            entry_id=entry_id,
            start_slot_id=start_slot.id,
            expected_slot_indices=expected_indices,
            actual_slot_indices=actual_indices,
        )
        return ()

    for first, second in zip(slots, slots[1:], strict=False):
        if first.end_time != second.start_time:
            _append_conflict(
                conflicts,
                "SLOT_TIME_GAP",
                "A session cannot continue across a break between time slots.",
                entry_id=entry_id,
                first_slot_id=first.id,
                second_slot_id=second.id,
            )
            return ()
    return slots


def _validate_room(
    *,
    resolved: _ResolvedAssignment,
    conflicts: list[TimetableConflict],
    entry_id: int | None,
) -> None:
    session = resolved.session
    room = resolved.room
    program = session.course_offering.curriculum_course.program_semester.study_program
    if program.faculty_id != resolved.run.scheduling_profile.faculty_id:
        _append_conflict(
            conflicts,
            "PROFILE_FACULTY_MISMATCH",
            "The session's faculty must match the run's scheduling profile.",
            entry_id=entry_id,
            course_session_id=session.id,
            session_faculty_id=program.faculty_id,
            profile_faculty_id=resolved.run.scheduling_profile.faculty_id,
        )
    if room.status != RoomStatus.ACTIVE:
        _append_conflict(
            conflicts,
            "ROOM_INACTIVE",
            "The assigned room must be active.",
            entry_id=entry_id,
            room_id=room.id,
        )
    if room.faculty_id != program.faculty_id:
        _append_conflict(
            conflicts,
            "ROOM_FACULTY_MISMATCH",
            "The assigned room must belong to the offering's faculty.",
            entry_id=entry_id,
            room_id=room.id,
            room_faculty_id=room.faculty_id,
            offering_faculty_id=program.faculty_id,
        )
    if session.required_room_id is not None and room.id != session.required_room_id:
        _append_conflict(
            conflicts,
            "REQUIRED_ROOM_MISMATCH",
            "The session must use its specifically required room.",
            entry_id=entry_id,
            required_room_id=session.required_room_id,
            assigned_room_id=room.id,
        )
    if session.required_room_type is not None and room.room_type != session.required_room_type:
        _append_conflict(
            conflicts,
            "ROOM_TYPE_MISMATCH",
            "The room type is incompatible with the session requirement.",
            entry_id=entry_id,
            required_room_type=session.required_room_type,
            assigned_room_type=room.room_type,
        )
    if session.component_type == ComponentType.LABORATORY and room.room_type != RoomType.LABORATORY:
        _append_conflict(
            conflicts,
            "LABORATORY_ROOM_REQUIRED",
            "Laboratory sessions must be assigned to laboratory rooms.",
            entry_id=entry_id,
            room_id=room.id,
        )
    required_capacity = resolved.student_count
    if required_capacity == 0:
        required_capacity = session.max_students or session.course_offering.expected_students or 0
    if required_capacity > room.capacity:
        _append_conflict(
            conflicts,
            "ROOM_CAPACITY_EXCEEDED",
            "The assigned room cannot hold the session's students.",
            entry_id=entry_id,
            room_id=room.id,
            required_capacity=required_capacity,
            room_capacity=room.capacity,
        )
    profile_capacity = _component_capacity(resolved.run.scheduling_profile, session)
    session_limit = session.max_students or profile_capacity
    allowed_capacity = min(profile_capacity, session_limit)
    if required_capacity > allowed_capacity:
        _append_conflict(
            conflicts,
            "SESSION_CAPACITY_EXCEEDED",
            "The assigned groups exceed the session or profile capacity limit.",
            entry_id=entry_id,
            required_capacity=required_capacity,
            allowed_capacity=allowed_capacity,
            is_splittable=session.is_splittable,
        )


def _window_contains(
    window_start: time,
    window_end: time,
    assignment_start: time,
    assignment_end: time,
) -> bool:
    return window_start <= assignment_start and window_end >= assignment_end


def _windows_overlap(
    first_start: time,
    first_end: time,
    second_start: time,
    second_end: time,
) -> bool:
    return first_start < second_end and first_end > second_start


def _validate_session_time_constraints(
    db: Session,
    *,
    resolved: _ResolvedAssignment,
    conflicts: list[TimetableConflict],
    entry_id: int | None,
) -> None:
    day = resolved.start_slot.day_of_week
    start = resolved.start_slot.start_time
    end = resolved.end_time
    constraints = tuple(
        db.scalars(
            select(CourseSessionTimeConstraint).where(
                CourseSessionTimeConstraint.course_session_id == resolved.session.id
            )
        ).all()
    )
    applicable = tuple(item for item in constraints if item.day_of_week in {None, day})
    forbidden = tuple(
        item for item in applicable if item.constraint_type == TimeConstraintType.FORBIDDEN_WINDOW
    )
    if any(_windows_overlap(start, end, item.start_time, item.end_time) for item in forbidden):
        _append_conflict(
            conflicts,
            "FORBIDDEN_SESSION_TIME",
            "The assignment overlaps a forbidden session window.",
            entry_id=entry_id,
            course_session_id=resolved.session.id,
        )
    allowed = tuple(
        item for item in applicable if item.constraint_type == TimeConstraintType.ALLOWED_WINDOW
    )
    if allowed and not any(
        _window_contains(item.start_time, item.end_time, start, end) for item in allowed
    ):
        _append_conflict(
            conflicts,
            "OUTSIDE_ALLOWED_SESSION_TIME",
            "The complete assignment must fit an allowed session window.",
            entry_id=entry_id,
            course_session_id=resolved.session.id,
        )
    fixed = tuple(
        item for item in constraints if item.constraint_type == TimeConstraintType.FIXED_WINDOW
    )
    if fixed and not any(
        item.day_of_week == day and item.start_time == start and item.end_time == end
        for item in fixed
    ):
        _append_conflict(
            conflicts,
            "FIXED_SESSION_TIME_MISMATCH",
            "The assignment must exactly match the fixed session window.",
            entry_id=entry_id,
            course_session_id=resolved.session.id,
        )


def _mapped_attribute(
    model_type: type[Any],
    attribute_name: str,
) -> InstrumentedAttribute[Any]:
    return cast(
        InstrumentedAttribute[Any],
        getattr(model_type, attribute_name),
    )


def _validate_availability(
    db: Session,
    *,
    model_type: type[Any],
    owner_field: Any,
    owner_id: int,
    academic_term_id: int,
    day_of_week: int,
    start_time: time,
    end_time: time,
    resource_code: str,
    resource_label: str,
    entry_id: int | None,
    conflicts: list[TimetableConflict],
) -> None:
    academic_term_column = _mapped_attribute(
        model_type,
        "academic_term_id",
    )
    day_column = _mapped_attribute(model_type, "day_of_week")
    windows = tuple(
        db.scalars(
            select(model_type).where(
                owner_field == owner_id,
                academic_term_column == academic_term_id,
                day_column == day_of_week,
            )
        ).all()
    )
    unavailable = tuple(
        item for item in windows if item.availability_type == AvailabilityType.UNAVAILABLE
    )
    if any(
        _windows_overlap(start_time, end_time, item.start_time, item.end_time)
        for item in unavailable
    ):
        _append_conflict(
            conflicts,
            f"{resource_code}_UNAVAILABLE",
            f"The assignment overlaps {resource_label} unavailability.",
            entry_id=entry_id,
            owner_id=owner_id,
        )
    available = tuple(
        item for item in windows if item.availability_type == AvailabilityType.AVAILABLE
    )
    if available and not any(
        _window_contains(
            item.start_time,
            item.end_time,
            start_time,
            end_time,
        )
        for item in available
    ):
        _append_conflict(
            conflicts,
            f"{resource_code}_OUTSIDE_AVAILABILITY",
            f"The complete assignment must fit {resource_label} availability.",
            entry_id=entry_id,
            owner_id=owner_id,
        )


def _group_ancestor_ids(db: Session, group_id: int) -> set[int]:
    ancestors: set[int] = set()
    group = require_by_id(db, StudentGroup, group_id, "Student group")
    parent_id = group.parent_group_id
    while parent_id is not None and parent_id not in ancestors:
        ancestors.add(parent_id)
        parent = require_by_id(db, StudentGroup, parent_id, "Student group")
        parent_id = parent.parent_group_id
    return ancestors


def _groups_conflict(
    db: Session,
    first_group_ids: frozenset[int],
    second_group_ids: frozenset[int],
) -> bool:
    if first_group_ids.intersection(second_group_ids):
        return True
    first_ancestors = {group_id: _group_ancestor_ids(db, group_id) for group_id in first_group_ids}
    second_ancestors = {
        group_id: _group_ancestor_ids(db, group_id) for group_id in second_group_ids
    }
    return any(
        first_id in second_ancestors[second_id] or second_id in first_ancestors[first_id]
        for first_id in first_group_ids
        for second_id in second_group_ids
    )


def _validate_session_assignments(
    db: Session,
    *,
    resolved: _ResolvedAssignment,
    conflicts: list[TimetableConflict],
    entry_id: int | None,
) -> None:
    session = resolved.session
    offering = session.course_offering
    curriculum = offering.curriculum_course
    staff_assignments = tuple(
        db.scalars(
            select(CourseSessionStaff).where(CourseSessionStaff.course_session_id == session.id)
        ).all()
    )
    if not staff_assignments:
        _append_conflict(
            conflicts,
            "MISSING_SESSION_STAFF",
            "A scheduled session requires at least one staff member.",
            entry_id=entry_id,
            course_session_id=session.id,
        )
    primary_count = sum(item.is_primary for item in staff_assignments)
    if primary_count != 1:
        _append_conflict(
            conflicts,
            "INVALID_PRIMARY_STAFF_COUNT",
            "A scheduled session requires exactly one primary staff member.",
            entry_id=entry_id,
            course_session_id=session.id,
            primary_staff_count=primary_count,
        )
    expected_roles = {
        ComponentType.LECTURE: TeachingRole.LECTURER,
        ComponentType.NUMERICAL: TeachingRole.NUMERICAL_INSTRUCTOR,
        ComponentType.LABORATORY: TeachingRole.LAB_INSTRUCTOR,
    }
    for assignment in staff_assignments:
        staff_member = require_by_id(
            db,
            StaffMember,
            assignment.staff_member_id,
            "Staff member",
        )
        if not staff_member.is_active:
            _append_conflict(
                conflicts,
                "STAFF_INACTIVE",
                "Scheduled staff members must remain active.",
                entry_id=entry_id,
                staff_member_id=staff_member.id,
            )
        qualification = db.scalar(
            select(StaffCourse)
            .where(
                StaffCourse.staff_member_id == staff_member.id,
                StaffCourse.course_id == curriculum.course_id,
                StaffCourse.is_active.is_(True),
            )
            .limit(1)
        )
        invalid_role = assignment.teaching_role != expected_roles[session.component_type]
        invalid_capability = (
            qualification is None
            or (assignment.teaching_role == TeachingRole.LECTURER and not qualification.can_lecture)
            or (
                assignment.teaching_role
                in {
                    TeachingRole.NUMERICAL_INSTRUCTOR,
                    TeachingRole.LAB_INSTRUCTOR,
                }
                and not qualification.can_assist
            )
        )
        if invalid_role or invalid_capability:
            _append_conflict(
                conflicts,
                "INVALID_STAFF_QUALIFICATION",
                "Teaching role and active course qualification must match.",
                entry_id=entry_id,
                staff_member_id=staff_member.id,
                course_session_id=session.id,
            )

    group_assignments = tuple(
        db.scalars(
            select(StudentGroup)
            .join(
                CourseSessionGroup,
                CourseSessionGroup.student_group_id == StudentGroup.id,
            )
            .where(CourseSessionGroup.course_session_id == session.id)
        ).all()
    )
    if not group_assignments:
        _append_conflict(
            conflicts,
            "MISSING_SESSION_GROUP",
            "A scheduled session requires at least one student group.",
            entry_id=entry_id,
            course_session_id=session.id,
        )
    for group in group_assignments:
        if (
            not group.is_active
            or group.academic_term_id != offering.academic_term_id
            or group.program_semester_id != curriculum.program_semester_id
        ):
            _append_conflict(
                conflicts,
                "INCOMPATIBLE_SESSION_GROUP",
                "Session groups must stay active and match its term and semester.",
                entry_id=entry_id,
                course_session_id=session.id,
                student_group_id=group.id,
            )


def _resolve_assignment(
    db: Session,
    *,
    timetable_run_id: int,
    course_session_id: int,
    room_id: int,
    start_slot_id: int,
    entry_id: int | None,
    conflicts: list[TimetableConflict],
) -> _ResolvedAssignment:
    run = require_by_id(db, TimetableRun, timetable_run_id, "Timetable run")
    session = require_by_id(
        db,
        CourseSession,
        course_session_id,
        "Course session",
    )
    room = require_by_id(db, Room, room_id, "Room")
    start_slot = require_by_id(db, TimeSlot, start_slot_id, "Start slot")
    if not session.is_active:
        _append_conflict(
            conflicts,
            "SESSION_INACTIVE",
            "A timetable entry requires an active course session.",
            entry_id=entry_id,
            course_session_id=session.id,
        )
    offering = session.course_offering
    if offering.academic_term_id != run.academic_term_id:
        _append_conflict(
            conflicts,
            "SESSION_TERM_MISMATCH",
            "The session and timetable run must belong to the same term.",
            entry_id=entry_id,
            course_session_id=session.id,
            run_academic_term_id=run.academic_term_id,
            offering_academic_term_id=offering.academic_term_id,
        )
    if offering.status != CourseOfferingStatus.READY:
        _append_conflict(
            conflicts,
            "OFFERING_NOT_READY",
            "Only READY course offerings may be scheduled.",
            entry_id=entry_id,
            course_offering_id=offering.id,
            course_offering_status=offering.status,
        )
    slots = _resolve_slots(
        db,
        run=run,
        session=session,
        start_slot=start_slot,
        conflicts=conflicts,
        entry_id=entry_id,
    )
    end_time = slots[-1].end_time if slots else start_slot.end_time
    staff_ids = frozenset(
        db.scalars(
            select(CourseSessionStaff.staff_member_id).where(
                CourseSessionStaff.course_session_id == session.id
            )
        ).all()
    )
    group_ids = frozenset(
        db.scalars(
            select(CourseSessionGroup.student_group_id).where(
                CourseSessionGroup.course_session_id == session.id
            )
        ).all()
    )
    return _ResolvedAssignment(
        run=run,
        session=session,
        room=room,
        start_slot=start_slot,
        slots=slots,
        end_time=end_time,
        staff_ids=staff_ids,
        group_ids=group_ids,
        student_count=_session_student_count(db, session.id),
    )


def collect_entry_conflicts(
    db: Session,
    *,
    timetable_run_id: int,
    course_session_id: int,
    occurrence_number: int,
    room_id: int,
    start_slot_id: int,
    exclude_entry_id: int | None = None,
) -> tuple[TimetableConflict, ...]:
    conflicts: list[TimetableConflict] = []
    resolved = _resolve_assignment(
        db,
        timetable_run_id=timetable_run_id,
        course_session_id=course_session_id,
        room_id=room_id,
        start_slot_id=start_slot_id,
        entry_id=exclude_entry_id,
        conflicts=conflicts,
    )
    session = resolved.session
    if occurrence_number <= 0 or occurrence_number > session.weekly_frequency:
        _append_conflict(
            conflicts,
            "INVALID_OCCURRENCE_NUMBER",
            "occurrence_number must be between 1 and weekly_frequency.",
            entry_id=exclude_entry_id,
            occurrence_number=occurrence_number,
            weekly_frequency=session.weekly_frequency,
        )
    _validate_room(
        resolved=resolved,
        conflicts=conflicts,
        entry_id=exclude_entry_id,
    )
    _validate_session_assignments(
        db,
        resolved=resolved,
        conflicts=conflicts,
        entry_id=exclude_entry_id,
    )
    _validate_session_time_constraints(
        db,
        resolved=resolved,
        conflicts=conflicts,
        entry_id=exclude_entry_id,
    )
    for staff_member_id in resolved.staff_ids:
        _validate_availability(
            db,
            model_type=StaffAvailability,
            owner_field=StaffAvailability.staff_member_id,
            owner_id=staff_member_id,
            academic_term_id=resolved.run.academic_term_id,
            day_of_week=resolved.start_slot.day_of_week,
            start_time=resolved.start_slot.start_time,
            end_time=resolved.end_time,
            resource_code="STAFF",
            resource_label="staff",
            entry_id=exclude_entry_id,
            conflicts=conflicts,
        )
    _validate_availability(
        db,
        model_type=RoomAvailability,
        owner_field=RoomAvailability.room_id,
        owner_id=resolved.room.id,
        academic_term_id=resolved.run.academic_term_id,
        day_of_week=resolved.start_slot.day_of_week,
        start_time=resolved.start_slot.start_time,
        end_time=resolved.end_time,
        resource_code="ROOM",
        resource_label="room",
        entry_id=exclude_entry_id,
        conflicts=conflicts,
    )

    statement = select(TimetableEntry).where(TimetableEntry.timetable_run_id == timetable_run_id)
    if exclude_entry_id is not None:
        statement = statement.where(TimetableEntry.id != exclude_entry_id)
    for other in db.scalars(statement).all():
        other_conflicts: list[TimetableConflict] = []
        other_resolved = _resolve_assignment(
            db,
            timetable_run_id=other.timetable_run_id,
            course_session_id=other.course_session_id,
            room_id=other.room_id,
            start_slot_id=other.start_slot_id,
            entry_id=other.id,
            conflicts=other_conflicts,
        )
        same_day = resolved.start_slot.day_of_week == other_resolved.start_slot.day_of_week
        overlaps = same_day and _windows_overlap(
            resolved.start_slot.start_time,
            resolved.end_time,
            other_resolved.start_slot.start_time,
            other_resolved.end_time,
        )
        if not overlaps:
            continue
        pair = tuple(
            sorted(entry_id for entry_id in (exclude_entry_id, other.id) if entry_id is not None)
        )
        if resolved.room.id == other_resolved.room.id:
            _append_conflict(
                conflicts,
                "ROOM_OVERLAP",
                "A room cannot host overlapping entries in one run.",
                entry_ids=pair,
                room_id=resolved.room.id,
            )
        shared_staff = sorted(resolved.staff_ids.intersection(other_resolved.staff_ids))
        if shared_staff:
            _append_conflict(
                conflicts,
                "STAFF_OVERLAP",
                "Staff cannot teach overlapping entries in one run.",
                entry_ids=pair,
                staff_member_ids=shared_staff,
            )
        if _groups_conflict(db, resolved.group_ids, other_resolved.group_ids):
            _append_conflict(
                conflicts,
                "STUDENT_GROUP_OVERLAP",
                "The same or an ancestor/descendant group cannot overlap.",
                entry_ids=pair,
            )
    return tuple(conflicts)


def _expected_sessions(
    db: Session,
    run: TimetableRun,
) -> tuple[CourseSession, ...]:
    return tuple(
        db.scalars(
            select(CourseSession)
            .join(
                CourseOffering,
                CourseOffering.id == CourseSession.course_offering_id,
            )
            .join(
                CurriculumCourse,
                CurriculumCourse.id == CourseOffering.curriculum_course_id,
            )
            .join(
                ProgramSemester,
                ProgramSemester.id == CurriculumCourse.program_semester_id,
            )
            .join(
                StudyProgram,
                StudyProgram.id == ProgramSemester.study_program_id,
            )
            .where(
                CourseOffering.academic_term_id == run.academic_term_id,
                CourseOffering.status == CourseOfferingStatus.READY,
                CourseSession.is_active.is_(True),
                StudyProgram.faculty_id == run.scheduling_profile.faculty_id,
            )
        ).all()
    )


def _slot_positions(db: Session, profile_id: int) -> dict[int, int]:
    slots = tuple(
        db.scalars(
            select(TimeSlot)
            .where(
                TimeSlot.scheduling_profile_id == profile_id,
                TimeSlot.is_active.is_(True),
            )
            .order_by(TimeSlot.day_of_week, TimeSlot.slot_index)
        ).all()
    )
    return {slot.id: index for index, slot in enumerate(slots)}


def _dependency_satisfied(
    dependency: CourseSessionDependency,
    predecessor: TimetableEntry,
    successor: TimetableEntry,
    slots: dict[int, TimeSlot],
    positions: dict[int, int],
) -> bool:
    predecessor_slot = slots[predecessor.start_slot_id]
    successor_slot = slots[successor.start_slot_id]
    predecessor_session = predecessor.course_session
    predecessor_end_position = (
        positions[predecessor.start_slot_id] + predecessor_session.duration_slots
    )
    successor_position = positions[successor.start_slot_id]
    if dependency.dependency_type == DependencyType.SAME_DAY:
        return predecessor_slot.day_of_week == successor_slot.day_of_week
    if dependency.dependency_type == DependencyType.DIFFERENT_DAY:
        return predecessor_slot.day_of_week != successor_slot.day_of_week
    if dependency.dependency_type == DependencyType.CONSECUTIVE:
        return (
            predecessor_slot.day_of_week == successor_slot.day_of_week
            and predecessor_end_position == successor_position
        )
    gap = successor_position - predecessor_end_position
    if gap < 0:
        return False
    if dependency.min_gap_slots is not None and gap < dependency.min_gap_slots:
        return False
    return not (dependency.max_gap_slots is not None and gap > dependency.max_gap_slots)


def _collect_dependency_conflicts(
    db: Session,
    *,
    run: TimetableRun,
    entries: tuple[TimetableEntry, ...],
    conflicts: list[TimetableConflict],
) -> None:
    by_session: dict[int, list[TimetableEntry]] = {}
    for entry in entries:
        by_session.setdefault(entry.course_session_id, []).append(entry)
    session_ids = set(by_session)
    if not session_ids:
        return
    dependencies = tuple(
        db.scalars(
            select(CourseSessionDependency).where(
                CourseSessionDependency.predecessor_session_id.in_(session_ids),
                CourseSessionDependency.successor_session_id.in_(session_ids),
            )
        ).all()
    )
    slots = {
        slot.id: slot
        for slot in db.scalars(
            select(TimeSlot).where(TimeSlot.scheduling_profile_id == run.scheduling_profile_id)
        ).all()
    }
    positions = _slot_positions(db, run.scheduling_profile_id)
    for dependency in dependencies:
        predecessors = by_session.get(dependency.predecessor_session_id, [])
        successors = by_session.get(dependency.successor_session_id, [])
        for successor in successors:
            satisfied = any(
                predecessor.start_slot_id in positions
                and successor.start_slot_id in positions
                and _dependency_satisfied(
                    dependency,
                    predecessor,
                    successor,
                    slots,
                    positions,
                )
                for predecessor in predecessors
            )
            if not satisfied:
                _append_conflict(
                    conflicts,
                    "DEPENDENCY_VIOLATION",
                    "No predecessor occurrence satisfies a session dependency.",
                    dependency_id=dependency.id,
                    successor_entry_id=successor.id,
                    dependency_type=dependency.dependency_type,
                )


def validate_timetable_run(
    db: Session,
    timetable_run_id: int,
    *,
    store_hard_conflicts: bool = False,
) -> TimetableValidationResult:
    run = require_by_id(db, TimetableRun, timetable_run_id, "Timetable run")
    conflicts: list[TimetableConflict] = []
    entries = tuple(
        db.scalars(
            select(TimetableEntry)
            .where(TimetableEntry.timetable_run_id == run.id)
            .order_by(
                TimetableEntry.course_session_id,
                TimetableEntry.occurrence_number,
            )
        ).all()
    )
    for entry in entries:
        for conflict in collect_entry_conflicts(
            db,
            timetable_run_id=entry.timetable_run_id,
            course_session_id=entry.course_session_id,
            occurrence_number=entry.occurrence_number,
            room_id=entry.room_id,
            start_slot_id=entry.start_slot_id,
            exclude_entry_id=entry.id,
        ):
            _append_conflict(
                conflicts,
                conflict.code,
                conflict.message,
                **conflict.details,
            )

    expected_sessions = _expected_sessions(db, run)
    expected_occurrences = sum(session.weekly_frequency for session in expected_sessions)
    entries_by_session: dict[int, set[int]] = {}
    for entry in entries:
        entries_by_session.setdefault(entry.course_session_id, set()).add(entry.occurrence_number)
    expected_ids = {session.id for session in expected_sessions}
    for session in expected_sessions:
        expected_numbers = set(range(1, session.weekly_frequency + 1))
        actual_numbers = entries_by_session.get(session.id, set())
        if actual_numbers != expected_numbers:
            _append_conflict(
                conflicts,
                "INCOMPLETE_SESSION_OCCURRENCES",
                "Every active READY session needs exactly its weekly occurrences.",
                course_session_id=session.id,
                expected_occurrences=sorted(expected_numbers),
                actual_occurrences=sorted(actual_numbers),
            )
    for unexpected_session_id in set(entries_by_session).difference(expected_ids):
        _append_conflict(
            conflicts,
            "UNEXPECTED_SESSION_ENTRY",
            "The run contains a session outside its READY term/faculty input.",
            course_session_id=unexpected_session_id,
        )
    _collect_dependency_conflicts(
        db,
        run=run,
        entries=entries,
        conflicts=conflicts,
    )
    result = TimetableValidationResult(
        timetable_run_id=run.id,
        hard_conflicts=tuple(conflicts),
        expected_occurrences=expected_occurrences,
        actual_entries=len(entries),
    )
    if store_hard_conflicts:
        run.hard_conflicts = result.hard_conflict_count
        db.flush()
    return result
