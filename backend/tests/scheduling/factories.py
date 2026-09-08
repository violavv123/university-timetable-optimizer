from __future__ import annotations

from dataclasses import replace

from app.models.enums import (
    ComponentType,
    RoomType,
    StudentGroupType,
    TeachingRole,
)
from app.scheduling.domain import (
    CandidateRoom,
    SchedulingInput,
    SchedulingSlot,
    SchedulingWeights,
    SessionOccurrence,
    StaffAssignment,
    StartCandidate,
    StudentGroupData,
)


def make_slots(*, days: tuple[int, ...] = (1, 2), per_day: int = 4) -> tuple[SchedulingSlot, ...]:
    slots: list[SchedulingSlot] = []
    for day_rank, day in enumerate(days):
        for slot_index in range(per_day):
            start = 8 * 60 + slot_index * 45
            slots.append(
                SchedulingSlot(
                    id=day * 100 + slot_index,
                    day_of_week=day,
                    slot_index=slot_index,
                    start_minute=start,
                    end_minute=start + 45,
                    week_index=day_rank * per_day + slot_index,
                )
            )
    return tuple(slots)


def make_starts(
    slots: tuple[SchedulingSlot, ...],
    *,
    duration_slots: int = 1,
) -> tuple[StartCandidate, ...]:
    by_position = {(slot.day_of_week, slot.slot_index): slot for slot in slots}
    starts: list[StartCandidate] = []
    for first in slots:
        occupied = tuple(
            by_position.get((first.day_of_week, first.slot_index + offset))
            for offset in range(duration_slots)
        )
        if any(slot is None for slot in occupied):
            continue
        complete = tuple(slot for slot in occupied if slot is not None)
        if any(
            previous.end_minute != current.start_minute
            for previous, current in zip(complete, complete[1:], strict=False)
        ):
            continue
        starts.append(
            StartCandidate(
                start_slot_id=first.id,
                day_of_week=first.day_of_week,
                start_minute=first.start_minute,
                end_minute=complete[-1].end_minute,
                week_index=first.week_index,
                occupied_slot_ids=tuple(slot.id for slot in complete),
            )
        )
    return tuple(starts)


def make_groups() -> tuple[StudentGroupData, ...]:
    return (
        StudentGroupData(1, 1, 1, None, StudentGroupType.COHORT, 20, True),
        StudentGroupData(2, 1, 1, 1, StudentGroupType.LECTURE_GROUP, 20, True),
        StudentGroupData(3, 1, 1, 2, StudentGroupType.NUMERICAL_GROUP, 20, True),
        StudentGroupData(4, 1, 1, 3, StudentGroupType.LAB_GROUP, 20, True),
    )


def make_occurrence(
    *,
    session_id: int = 1,
    occurrence_number: int = 1,
    weekly_frequency: int = 1,
    duration_slots: int = 1,
    slots: tuple[SchedulingSlot, ...] | None = None,
    room_ids: frozenset[int] = frozenset({1}),
    direct_group_ids: frozenset[int] = frozenset({2}),
    student_resource_ids: frozenset[int] = frozenset({4}),
    staff_id: int = 1,
    component_type: ComponentType = ComponentType.LECTURE,
    level_code: str = "BSC",
    demand: int = 20,
) -> SessionOccurrence:
    slots = slots or make_slots()
    starts = make_starts(slots, duration_slots=duration_slots)
    role = {
        ComponentType.LECTURE: TeachingRole.LECTURER,
        ComponentType.NUMERICAL: TeachingRole.NUMERICAL_INSTRUCTOR,
        ComponentType.LABORATORY: TeachingRole.LAB_INSTRUCTOR,
    }[component_type]
    required_type = (
        RoomType.LABORATORY if component_type == ComponentType.LABORATORY else RoomType.GENERAL_ROOM
    )
    return SessionOccurrence(
        session_id=session_id,
        occurrence_number=occurrence_number,
        weekly_frequency=weekly_frequency,
        duration_slots=duration_slots,
        duration_minutes=duration_slots * 45,
        component_type=component_type,
        curriculum_periods=weekly_frequency * duration_slots,
        demand=demand,
        calculated_attendance=demand,
        offering_expected_students=demand,
        declared_max_students=demand,
        required_room_type=required_type,
        required_room_id=None,
        program_id=1,
        program_semester_id=1,
        academic_term_id=1,
        level_code=level_code,
        direct_group_ids=direct_group_ids,
        student_resource_ids=student_resource_ids,
        staff_ids=frozenset({staff_id}),
        staff_assignments=(
            StaffAssignment(
                staff_member_id=staff_id,
                teaching_role=role,
                is_primary=True,
                is_active=True,
                is_qualified=True,
            ),
        ),
        time_constraints=(),
        start_candidates=starts,
        compatible_room_ids=room_ids,
        allowed_start_room_pairs=frozenset(
            (start.start_slot_id, room_id) for start in starts for room_id in room_ids
        ),
    )


def make_input(
    *occurrences: SessionOccurrence,
    slots: tuple[SchedulingSlot, ...] | None = None,
    rooms: tuple[CandidateRoom, ...] | None = None,
    parameters: dict[str, object] | None = None,
) -> SchedulingInput:
    slots = slots or make_slots()
    if not occurrences:
        occurrences = (make_occurrence(slots=slots),)
    rooms = rooms or (
        CandidateRoom(1, "R-30", 30, RoomType.GENERAL_ROOM),
        CandidateRoom(2, "R-60", 60, RoomType.GENERAL_ROOM),
        CandidateRoom(3, "LAB-20", 20, RoomType.LABORATORY),
    )
    return SchedulingInput(
        timetable_run_id=1,
        academic_term_id=1,
        scheduling_profile_id=1,
        faculty_id=1,
        slot_minutes=45,
        max_lecture_students=60,
        max_numerical_students=40,
        max_lab_students=20,
        slots=slots,
        rooms=rooms,
        groups=make_groups(),
        occurrences=tuple(occurrences),
        dependencies=(),
        locked_assignments=(),
        staff_availability={},
        room_availability={},
        program_room_preferences={},
        historical_rooms={},
        weights=SchedulingWeights(1, 1, 1, 1, 1),
        parameters=dict(parameters or {}),
    )


def with_rooms(
    occurrence: SessionOccurrence,
    room_ids: frozenset[int],
) -> SessionOccurrence:
    return replace(
        occurrence,
        compatible_room_ids=room_ids,
        allowed_start_room_pairs=frozenset(
            (start.start_slot_id, room_id)
            for start in occurrence.start_candidates
            for room_id in room_ids
        ),
    )
