from __future__ import annotations

from dataclasses import replace

from app.models.enums import ComponentType, RoomType, TeachingRole
from app.scheduling.domain import (
    CandidateRoom,
    LockedAssignment,
    SchedulingInput,
    SchedulingSlot,
    SchedulingWeights,
    SessionDependency,
    SessionOccurrence,
    StaffAssignment,
    StartCandidate,
)


def slot(
    slot_id: int,
    *,
    day: int,
    index: int,
    start_minute: int,
    week_index: int,
) -> SchedulingSlot:
    return SchedulingSlot(
        id=slot_id,
        day_of_week=day,
        slot_index=index,
        start_minute=start_minute,
        end_minute=start_minute + 45,
        week_index=week_index,
    )


def start(value: SchedulingSlot) -> StartCandidate:
    return StartCandidate(
        start_slot_id=value.id,
        day_of_week=value.day_of_week,
        start_minute=value.start_minute,
        end_minute=value.end_minute,
        week_index=value.week_index,
        occupied_slot_ids=(value.id,),
    )


def room(room_id: int, code: str, capacity: int) -> CandidateRoom:
    return CandidateRoom(
        id=room_id,
        code=code,
        capacity=capacity,
        room_type=RoomType.GENERAL_ROOM,
    )


def occurrence(
    session_id: int,
    candidate: StartCandidate,
    candidate_room: CandidateRoom,
    *,
    demand: int = 30,
    staff_id: int | None = None,
    level_code: str = "BSc",
) -> SessionOccurrence:
    assigned_staff_id = staff_id if staff_id is not None else session_id
    return SessionOccurrence(
        session_id=session_id,
        occurrence_number=1,
        weekly_frequency=1,
        duration_slots=1,
        duration_minutes=45,
        component_type=ComponentType.LECTURE,
        curriculum_periods=1,
        demand=demand,
        calculated_attendance=0,
        offering_expected_students=demand,
        declared_max_students=None,
        required_room_type=None,
        required_room_id=None,
        program_id=1,
        program_semester_id=1,
        academic_term_id=1,
        level_code=level_code,
        direct_group_ids=frozenset(),
        student_resource_ids=frozenset(),
        staff_ids=frozenset({assigned_staff_id}),
        staff_assignments=(
            StaffAssignment(
                staff_member_id=assigned_staff_id,
                teaching_role=TeachingRole.LECTURER,
                is_primary=True,
                is_active=True,
                is_qualified=True,
            ),
        ),
        time_constraints=(),
        start_candidates=(candidate,),
        compatible_room_ids=frozenset({candidate_room.id}),
        allowed_start_room_pairs=frozenset({(candidate.start_slot_id, candidate_room.id)}),
    )


def scheduling_input(
    *,
    slots: tuple[SchedulingSlot, ...],
    rooms: tuple[CandidateRoom, ...],
    occurrences: tuple[SessionOccurrence, ...],
    dependencies: tuple[SessionDependency, ...] = (),
    locked_assignments: tuple[LockedAssignment, ...] = (),
    parameters: dict[str, object] | None = None,
) -> SchedulingInput:
    return SchedulingInput(
        timetable_run_id=1,
        academic_term_id=1,
        scheduling_profile_id=1,
        faculty_id=1,
        slot_minutes=45,
        max_lecture_students=300,
        max_numerical_students=60,
        max_lab_students=40,
        slots=slots,
        rooms=rooms,
        groups=(),
        occurrences=occurrences,
        dependencies=dependencies,
        locked_assignments=locked_assignments,
        staff_availability={},
        room_availability={},
        program_room_preferences={},
        historical_rooms={},
        weights=SchedulingWeights(
            preferred_room=1,
            historical_room=1,
            student_gap=1,
            staff_gap=1,
            late_hour=1,
            unused_seat=1,
        ),
        parameters=dict(parameters or {}),
    )


def with_candidate_room(
    value: SessionOccurrence,
    candidate_room: CandidateRoom,
) -> SessionOccurrence:
    """Return an occurrence adjusted to a different single feasible room."""

    return replace(
        value,
        compatible_room_ids=frozenset({candidate_room.id}),
        allowed_start_room_pairs=frozenset(
            {(value.start_candidates[0].start_slot_id, candidate_room.id)}
        ),
    )
