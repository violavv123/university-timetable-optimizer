from dataclasses import replace

from app.models.enums import DependencyType, TimeConstraintType, TimetableRunStatus
from app.scheduling.cp_sat_solver import CpSatTimetableSolver
from app.scheduling.domain import (
    LockedAssignment,
    RoomStrategy,
    SchedulingSlot,
    SessionDependency,
    SessionTimeConstraint,
)
from app.scheduling.greedy_solver import GreedyTimetableSolver
from app.scheduling.result_validator import validate_solver_result
from tests.scheduling.factories import make_input, make_occurrence, make_slots


def test_greedy_spreads_repeated_occurrences_across_days() -> None:
    slots = make_slots(days=(1, 2), per_day=2)
    occurrences = tuple(
        make_occurrence(
            occurrence_number=number,
            weekly_frequency=2,
            slots=slots,
        )
        for number in (1, 2)
    )
    data = make_input(*occurrences, slots=slots)

    result = GreedyTimetableSolver(RoomStrategy.BFD).solve(data)

    assert result.status == TimetableRunStatus.SUCCEEDED
    days = {
        data.slot_by_id[assignment.start_slot_id].day_of_week for assignment in result.assignments
    }
    assert days == {1, 2}
    assert validate_solver_result(data, result.assignments).is_valid


def test_greedy_can_place_a_predecessor_before_a_locked_successor() -> None:
    slots = make_slots(days=(1,), per_day=3)
    predecessor = replace(
        make_occurrence(session_id=1, slots=slots, staff_id=1),
        start_candidates=(make_occurrence(slots=slots).start_candidates[0],),
    )
    predecessor = replace(
        predecessor,
        allowed_start_room_pairs=frozenset({(predecessor.start_candidates[0].start_slot_id, 1)}),
    )
    successor_base = make_occurrence(
        session_id=2,
        slots=slots,
        staff_id=2,
        student_resource_ids=frozenset({3}),
    )
    successor = replace(
        successor_base,
        start_candidates=(successor_base.start_candidates[1],),
        allowed_start_room_pairs=frozenset({(successor_base.start_candidates[1].start_slot_id, 2)}),
        compatible_room_ids=frozenset({2}),
    )
    data = replace(
        make_input(predecessor, successor, slots=slots),
        dependencies=(SessionDependency(1, 1, 2, DependencyType.PRECEDES),),
        locked_assignments=(
            LockedAssignment(2, 1, 2, successor.start_candidates[0].start_slot_id),
        ),
    )

    result = GreedyTimetableSolver(RoomStrategy.FFD).solve(data)

    assert result.status == TimetableRunStatus.SUCCEEDED
    assert validate_solver_result(data, result.assignments).is_valid


def test_cp_sat_enforces_room_staff_student_and_spread_constraints() -> None:
    slots = make_slots(days=(1, 2), per_day=3)
    repeated = tuple(
        make_occurrence(
            session_id=1,
            occurrence_number=number,
            weekly_frequency=2,
            slots=slots,
        )
        for number in (1, 2)
    )
    competing = make_occurrence(
        session_id=2,
        slots=slots,
        staff_id=1,
        student_resource_ids=frozenset({4}),
    )
    data = make_input(*repeated, competing, slots=slots)

    result = CpSatTimetableSolver().solve(data)

    assert result.status == TimetableRunStatus.SUCCEEDED
    assert validate_solver_result(data, result.assignments).is_valid
    repeated_days = {
        data.slot_by_id[assignment.start_slot_id].day_of_week
        for assignment in result.assignments
        if assignment.course_session_id == 1
    }
    assert repeated_days == {1, 2}


def test_cp_sat_treats_master_evening_window_as_a_soft_preference() -> None:
    slots = (
        SchedulingSlot(100, 1, 0, 8 * 60, 8 * 60 + 45, 0),
        SchedulingSlot(101, 1, 1, 17 * 60, 17 * 60 + 45, 1),
    )
    occurrence = replace(
        make_occurrence(slots=slots, level_code="MSC"),
        time_constraints=(
            SessionTimeConstraint(
                day_of_week=None,
                start_minute=17 * 60,
                end_minute=20 * 60,
                constraint_type=TimeConstraintType.PREFERRED_WINDOW,
                preference_weight=20,
            ),
        ),
    )
    data = make_input(occurrence, slots=slots)

    result = CpSatTimetableSolver().solve(data)

    assert result.status == TimetableRunStatus.SUCCEEDED
    assert result.assignments[0].start_slot_id == 101
