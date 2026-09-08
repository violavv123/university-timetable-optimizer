from __future__ import annotations

from collections import defaultdict
from datetime import time

from app.models.course import Course
from app.models.course_offering import CourseOffering
from app.models.course_session import CourseSession
from app.models.course_session_dependency import CourseSessionDependency
from app.models.course_session_group import CourseSessionGroup
from app.models.course_session_staff import CourseSessionStaff
from app.models.curriculum_course import CurriculumCourse
from app.models.enums import (
    AvailabilityType,
    ComponentType,
    CourseOfferingStatus,
    RoomStatus,
    TeachingRole,
    TimeConstraintType,
    TimetableRunStatus,
)
from app.models.level import Level
from app.models.program_room_preference import ProgramRoomPreference
from app.models.program_semester import ProgramSemester
from app.models.room import Room
from app.models.room_availability import RoomAvailability
from app.models.scheduling_profile import SchedulingProfile
from app.models.staff_availability import StaffAvailability
from app.models.staff_course import StaffCourse
from app.models.student_group import StudentGroup
from app.models.study_program import StudyProgram
from app.models.time_slot import TimeSlot
from app.models.timetable_entry import TimetableEntry
from app.models.timetable_run import TimetableRun
from app.scheduling.domain import (
    AvailabilityWindow,
    CandidateRoom,
    LockedAssignment,
    SchedulingInput,
    SchedulingSlot,
    SchedulingWeights,
    SessionDependency,
    SessionOccurrence,
    SessionTimeConstraint,
    StaffAssignment,
    StartCandidate,
    StudentGroupData,
)
from sqlalchemy import select
from sqlalchemy.orm import Session, selectinload


def _minute(value: time) -> int:
    return value.hour * 60 + value.minute


def _overlaps(start: int, end: int, window_start: int, window_end: int) -> bool:
    return start < window_end and end > window_start


def _contains(window_start: int, window_end: int, start: int, end: int) -> bool:
    return window_start <= start and end <= window_end


def _hard_availability_allows(
    windows: tuple[AvailabilityWindow, ...],
    day_of_week: int,
    start_minute: int,
    end_minute: int,
) -> bool:
    unavailable = (
        window
        for window in windows
        if window.availability_type == AvailabilityType.UNAVAILABLE
        and window.day_of_week == day_of_week
    )
    if any(
        _overlaps(start_minute, end_minute, window.start_minute, window.end_minute)
        for window in unavailable
    ):
        return False

    available = tuple(
        window for window in windows if window.availability_type == AvailabilityType.AVAILABLE
    )
    if not available:
        return True
    return any(
        window.day_of_week == day_of_week
        and _contains(window.start_minute, window.end_minute, start_minute, end_minute)
        for window in available
    )


def _hard_session_time_allows(
    constraints: tuple[SessionTimeConstraint, ...],
    day_of_week: int,
    start_minute: int,
    end_minute: int,
) -> bool:
    forbidden = (
        constraint
        for constraint in constraints
        if constraint.constraint_type == TimeConstraintType.FORBIDDEN_WINDOW
        and constraint.day_of_week in {None, day_of_week}
    )
    if any(
        _overlaps(
            start_minute,
            end_minute,
            constraint.start_minute,
            constraint.end_minute,
        )
        for constraint in forbidden
    ):
        return False

    allowed = tuple(
        constraint
        for constraint in constraints
        if constraint.constraint_type == TimeConstraintType.ALLOWED_WINDOW
    )
    if allowed and not any(
        constraint.day_of_week in {None, day_of_week}
        and _contains(
            constraint.start_minute,
            constraint.end_minute,
            start_minute,
            end_minute,
        )
        for constraint in allowed
    ):
        return False

    fixed = tuple(
        constraint
        for constraint in constraints
        if constraint.constraint_type == TimeConstraintType.FIXED_WINDOW
    )
    if fixed and not any(
        constraint.day_of_week == day_of_week
        and constraint.start_minute == start_minute
        and end_minute <= constraint.end_minute
        for constraint in fixed
    ):
        return False
    return True


def _availability_windows(
    rows: tuple[StaffAvailability | RoomAvailability, ...],
    owner_attribute: str,
) -> dict[int, tuple[AvailabilityWindow, ...]]:
    by_owner: dict[int, list[AvailabilityWindow]] = defaultdict(list)
    for row in rows:
        owner_id = int(getattr(row, owner_attribute))
        by_owner[owner_id].append(
            AvailabilityWindow(
                owner_id=owner_id,
                day_of_week=row.day_of_week,
                start_minute=_minute(row.start_time),
                end_minute=_minute(row.end_time),
                availability_type=row.availability_type,
                preference_weight=row.preference_weight or 0,
            )
        )
    return {owner_id: tuple(windows) for owner_id, windows in by_owner.items()}


def _ancestors(
    group_id: int,
    groups: dict[int, StudentGroupData],
) -> tuple[int, ...]:
    result: list[int] = []
    seen = {group_id}
    parent_id = groups[group_id].parent_group_id
    while parent_id is not None and parent_id in groups and parent_id not in seen:
        result.append(parent_id)
        seen.add(parent_id)
        parent_id = groups[parent_id].parent_group_id
    return tuple(result)


def _leaf_descendants(
    group_id: int,
    children: dict[int, tuple[int, ...]],
) -> frozenset[int]:
    direct_children = children.get(group_id, ())
    if not direct_children:
        return frozenset({group_id})
    leaves: set[int] = set()
    pending = list(direct_children)
    seen = {group_id}
    while pending:
        child_id = pending.pop()
        if child_id in seen:
            continue
        seen.add(child_id)
        grandchildren = children.get(child_id, ())
        if grandchildren:
            pending.extend(grandchildren)
        else:
            leaves.add(child_id)
    return frozenset(leaves or {group_id})


def _attendance(
    direct_group_ids: frozenset[int],
    groups: dict[int, StudentGroupData],
) -> int:
    # If malformed input links both a parent and descendant, count the parent
    # only. The input validator still rejects that ambiguous relationship.
    roots = {
        group_id
        for group_id in direct_group_ids
        if group_id in groups and not direct_group_ids.intersection(_ancestors(group_id, groups))
    }
    return sum(groups[group_id].student_count for group_id in roots)


def _start_candidates(
    *,
    duration_slots: int,
    slots: tuple[SchedulingSlot, ...],
    constraints: tuple[SessionTimeConstraint, ...],
    staff_ids: frozenset[int],
    staff_availability: dict[int, tuple[AvailabilityWindow, ...]],
) -> tuple[StartCandidate, ...]:
    by_day_and_index = {(slot.day_of_week, slot.slot_index): slot for slot in slots}
    result: list[StartCandidate] = []
    for first in slots:
        occupied: list[SchedulingSlot] = []
        for offset in range(duration_slots):
            slot = by_day_and_index.get((first.day_of_week, first.slot_index + offset))
            if slot is None:
                occupied = []
                break
            occupied.append(slot)
        if not occupied:
            continue
        if any(
            previous.end_minute != current.start_minute
            for previous, current in zip(occupied, occupied[1:], strict=False)
        ):
            continue
        end_minute = occupied[-1].end_minute
        if not _hard_session_time_allows(
            constraints,
            first.day_of_week,
            first.start_minute,
            end_minute,
        ):
            continue
        if any(
            not _hard_availability_allows(
                staff_availability.get(staff_id, ()),
                first.day_of_week,
                first.start_minute,
                end_minute,
            )
            for staff_id in staff_ids
        ):
            continue
        result.append(
            StartCandidate(
                start_slot_id=first.id,
                day_of_week=first.day_of_week,
                start_minute=first.start_minute,
                end_minute=end_minute,
                week_index=first.week_index,
                occupied_slot_ids=tuple(slot.id for slot in occupied),
            )
        )
    return tuple(result)


def _curriculum_periods(session: CourseSession) -> int:
    curriculum = session.course_offering.curriculum_course
    if session.component_type == ComponentType.LECTURE:
        return curriculum.lecture_periods_per_week
    if session.component_type == ComponentType.NUMERICAL:
        return curriculum.numerical_periods_per_week
    return curriculum.laboratory_periods_per_week


def load_scheduling_input(
    db: Session,
    run: TimetableRun,
) -> SchedulingInput:
    profile = db.scalar(
        select(SchedulingProfile).where(SchedulingProfile.id == run.scheduling_profile_id)
    )
    if profile is None:
        raise ValueError(f"Scheduling profile {run.scheduling_profile_id} does not exist.")

    slot_rows = tuple(
        db.scalars(
            select(TimeSlot)
            .where(
                TimeSlot.scheduling_profile_id == profile.id,
                TimeSlot.is_active.is_(True),
            )
            .order_by(TimeSlot.day_of_week, TimeSlot.slot_index)
        ).all()
    )
    days = sorted({slot.day_of_week for slot in slot_rows})
    day_rank = {day: index for index, day in enumerate(days)}
    day_stride = max((slot.slot_index for slot in slot_rows), default=0) + 1
    slots = tuple(
        SchedulingSlot(
            id=slot.id,
            day_of_week=slot.day_of_week,
            slot_index=slot.slot_index,
            start_minute=_minute(slot.start_time),
            end_minute=_minute(slot.end_time),
            week_index=day_rank[slot.day_of_week] * day_stride + slot.slot_index,
        )
        for slot in slot_rows
    )

    room_rows = tuple(
        db.scalars(
            select(Room)
            .where(
                Room.faculty_id == profile.faculty_id,
                Room.status == RoomStatus.ACTIVE,
            )
            .order_by(Room.capacity, Room.code)
        ).all()
    )
    rooms = tuple(
        CandidateRoom(
            id=room.id,
            code=room.code,
            capacity=room.capacity,
            room_type=room.room_type,
        )
        for room in room_rows
    )

    all_group_rows = tuple(db.scalars(select(StudentGroup)).all())
    groups = {
        group.id: StudentGroupData(
            id=group.id,
            program_semester_id=group.program_semester_id,
            academic_term_id=group.academic_term_id,
            parent_group_id=group.parent_group_id,
            group_type=group.group_type,
            student_count=group.student_count,
            is_active=group.is_active,
        )
        for group in all_group_rows
    }
    child_lists: dict[int, list[int]] = defaultdict(list)
    for group in groups.values():
        if (
            group.parent_group_id is not None
            and group.is_active
            and group.academic_term_id == run.academic_term_id
        ):
            child_lists[group.parent_group_id].append(group.id)
    children = {parent_id: tuple(child_ids) for parent_id, child_ids in child_lists.items()}

    staff_availability = _availability_windows(
        tuple(
            db.scalars(
                select(StaffAvailability).where(
                    StaffAvailability.academic_term_id == run.academic_term_id
                )
            ).all()
        ),
        "staff_member_id",
    )
    room_availability = _availability_windows(
        tuple(
            db.scalars(
                select(RoomAvailability).where(
                    RoomAvailability.academic_term_id == run.academic_term_id
                )
            ).all()
        ),
        "room_id",
    )

    session_rows = tuple(
        db.scalars(
            select(CourseSession)
            .join(CourseOffering)
            .join(CurriculumCourse)
            .join(Course, Course.id == CurriculumCourse.course_id)
            .join(ProgramSemester)
            .join(StudyProgram)
            .join(Level)
            .where(
                CourseOffering.academic_term_id == run.academic_term_id,
                CourseOffering.status == CourseOfferingStatus.READY,
                CourseSession.is_active.is_(True),
                CurriculumCourse.is_active.is_(True),
                CurriculumCourse.requires_timetable.is_(True),
                Course.is_active.is_(True),
                ProgramSemester.is_active.is_(True),
                StudyProgram.is_active.is_(True),
                StudyProgram.faculty_id == profile.faculty_id,
            )
            .options(
                selectinload(CourseSession.group_assignments).selectinload(
                    CourseSessionGroup.student_group
                ),
                selectinload(CourseSession.staff_assignments).selectinload(
                    CourseSessionStaff.staff_member
                ),
                selectinload(CourseSession.time_constraints),
            )
            .order_by(CourseSession.id)
        )
        .unique()
        .all()
    )

    course_ids = {session.course_offering.curriculum_course.course_id for session in session_rows}
    qualification_rows = (
        tuple(db.scalars(select(StaffCourse).where(StaffCourse.course_id.in_(course_ids))).all())
        if course_ids
        else ()
    )
    qualifications = {
        (qualification.staff_member_id, qualification.course_id): qualification
        for qualification in qualification_rows
    }

    occurrence_rows: list[SessionOccurrence] = []
    for session in session_rows:
        curriculum = session.course_offering.curriculum_course
        program_semester = curriculum.program_semester
        program = program_semester.study_program
        direct_group_ids = frozenset(
            assignment.student_group_id for assignment in session.group_assignments
        )
        calculated_attendance = _attendance(direct_group_ids, groups)
        fallback_attendance = session.course_offering.expected_students or 0
        demand = session.max_students or calculated_attendance or fallback_attendance
        student_resource_ids = frozenset().union(
            *(
                _leaf_descendants(group_id, children)
                for group_id in direct_group_ids
                if group_id in groups
            )
        )
        staff_assignments: list[StaffAssignment] = []
        for assignment in session.staff_assignments:
            staff = assignment.staff_member
            qualification = qualifications.get((staff.id, curriculum.course_id))
            if assignment.teaching_role == TeachingRole.LECTURER:
                is_qualified = bool(
                    qualification and qualification.is_active and qualification.can_lecture
                )
            else:
                is_qualified = bool(
                    qualification and qualification.is_active and qualification.can_assist
                )
            staff_assignments.append(
                StaffAssignment(
                    staff_member_id=staff.id,
                    teaching_role=assignment.teaching_role,
                    is_primary=assignment.is_primary,
                    is_active=staff.is_active,
                    is_qualified=is_qualified,
                )
            )
        staff_ids = frozenset(assignment.staff_member_id for assignment in staff_assignments)
        constraints = tuple(
            SessionTimeConstraint(
                day_of_week=constraint.day_of_week,
                start_minute=_minute(constraint.start_time),
                end_minute=_minute(constraint.end_time),
                constraint_type=constraint.constraint_type,
                preference_weight=constraint.preference_weight or 0,
            )
            for constraint in session.time_constraints
        )
        starts = _start_candidates(
            duration_slots=session.duration_slots,
            slots=slots,
            constraints=constraints,
            staff_ids=staff_ids,
            staff_availability=staff_availability,
        )
        compatible_rooms = tuple(
            room
            for room in rooms
            if room.capacity >= demand
            and (session.required_room_type is None or room.room_type == session.required_room_type)
            and (
                session.component_type != ComponentType.LABORATORY
                or room.room_type.value == "LABORATORY"
            )
            and (session.required_room_id is None or room.id == session.required_room_id)
        )
        allowed_pairs = frozenset(
            (start.start_slot_id, room.id)
            for start in starts
            for room in compatible_rooms
            if _hard_availability_allows(
                room_availability.get(room.id, ()),
                start.day_of_week,
                start.start_minute,
                start.end_minute,
            )
        )
        duration_minutes = session.duration_slots * profile.slot_minutes
        for occurrence_number in range(1, session.weekly_frequency + 1):
            occurrence_rows.append(
                SessionOccurrence(
                    session_id=session.id,
                    occurrence_number=occurrence_number,
                    weekly_frequency=session.weekly_frequency,
                    duration_slots=session.duration_slots,
                    duration_minutes=duration_minutes,
                    component_type=session.component_type,
                    curriculum_periods=_curriculum_periods(session),
                    demand=demand,
                    calculated_attendance=calculated_attendance,
                    offering_expected_students=(session.course_offering.expected_students),
                    declared_max_students=session.max_students,
                    required_room_type=session.required_room_type,
                    required_room_id=session.required_room_id,
                    program_id=program.id,
                    program_semester_id=program_semester.id,
                    academic_term_id=session.course_offering.academic_term_id,
                    level_code=program.level.code,
                    direct_group_ids=direct_group_ids,
                    student_resource_ids=student_resource_ids,
                    staff_ids=staff_ids,
                    staff_assignments=tuple(staff_assignments),
                    time_constraints=constraints,
                    start_candidates=starts,
                    compatible_room_ids=frozenset(room.id for room in compatible_rooms),
                    allowed_start_room_pairs=allowed_pairs,
                )
            )

    session_ids = {session.id for session in session_rows}
    dependency_rows = (
        tuple(
            db.scalars(
                select(CourseSessionDependency).where(
                    CourseSessionDependency.predecessor_session_id.in_(session_ids),
                    CourseSessionDependency.successor_session_id.in_(session_ids),
                )
            ).all()
        )
        if session_ids
        else ()
    )
    dependencies = tuple(
        SessionDependency(
            id=dependency.id,
            predecessor_session_id=dependency.predecessor_session_id,
            successor_session_id=dependency.successor_session_id,
            dependency_type=dependency.dependency_type,
            min_gap_slots=dependency.min_gap_slots,
            max_gap_slots=dependency.max_gap_slots,
        )
        for dependency in dependency_rows
    )

    locked_assignments = tuple(
        LockedAssignment(
            course_session_id=entry.course_session_id,
            occurrence_number=entry.occurrence_number,
            room_id=entry.room_id,
            start_slot_id=entry.start_slot_id,
        )
        for entry in db.scalars(
            select(TimetableEntry).where(
                TimetableEntry.timetable_run_id == run.id,
                TimetableEntry.is_locked.is_(True),
            )
        ).all()
    )

    preference_rows = tuple(
        db.scalars(
            select(ProgramRoomPreference)
            .join(StudyProgram)
            .where(
                StudyProgram.faculty_id == profile.faculty_id,
                ProgramRoomPreference.is_active.is_(True),
            )
        ).all()
    )
    program_preferences: dict[int, dict[int, int]] = defaultdict(dict)
    for preference in preference_rows:
        program_preferences[preference.study_program_id][preference.room_id] = (
            preference.penalty_weight
        )

    historical_rows = tuple(
        db.execute(
            select(TimetableEntry.course_session_id, TimetableEntry.room_id)
            .join(TimetableRun)
            .where(
                TimetableRun.academic_term_id == run.academic_term_id,
                TimetableRun.scheduling_profile_id == run.scheduling_profile_id,
                TimetableRun.status == TimetableRunStatus.SUCCEEDED,
                TimetableRun.is_published.is_(True),
                TimetableRun.id != run.id,
            )
        ).all()
    )
    historical: dict[int, set[int]] = defaultdict(set)
    for session_id, room_id in historical_rows:
        historical[session_id].add(room_id)

    return SchedulingInput(
        timetable_run_id=run.id,
        academic_term_id=run.academic_term_id,
        scheduling_profile_id=profile.id,
        faculty_id=profile.faculty_id,
        slot_minutes=profile.slot_minutes,
        max_lecture_students=profile.max_lecture_students,
        max_numerical_students=profile.max_numerical_students,
        max_lab_students=profile.max_lab_students,
        slots=slots,
        rooms=rooms,
        groups=tuple(groups.values()),
        occurrences=tuple(occurrence_rows),
        dependencies=dependencies,
        locked_assignments=locked_assignments,
        staff_availability=staff_availability,
        room_availability=room_availability,
        program_room_preferences=dict(program_preferences),
        historical_rooms={
            session_id: frozenset(room_ids) for session_id, room_ids in historical.items()
        },
        weights=SchedulingWeights(
            preferred_room=profile.preferred_room_weight,
            historical_room=profile.historical_room_weight,
            student_gap=profile.student_gap_weight,
            staff_gap=profile.staff_gap_weight,
            late_hour=profile.late_hour_weight,
            unused_seat=int(run.parameters.get("unused_seat_weight", 1)),
        ),
        parameters=dict(run.parameters),
    )


__all__ = ["load_scheduling_input"]
