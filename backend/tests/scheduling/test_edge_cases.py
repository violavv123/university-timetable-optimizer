from dataclasses import replace

from app.models.enums import (
    DependencyType,
    TimeConstraintType,
    TimetableRunStatus,
)
from app.scheduling.domain import (
    LockedAssignment,
    RoomStrategy,
    SchedulingInput,
    SessionDependency,
    SessionTimeConstraint,
    SolverAssignment,
)
from app.scheduling.greedy_solver import GreedyTimetableSolver
from app.scheduling.input_validator import validate_scheduling_input
from app.scheduling.result_validator import validate_solver_result
from tests.scheduling.factories import occurrence, room, scheduling_input, slot, start


def _issue_codes(data: SchedulingInput) -> set[str]:
    result = validate_scheduling_input(data)
    return {issue.code for issue in result.issues}


def test_room_capacity_smaller_than_student_demand_is_rejected() -> None:
    time_slot = slot(1, day=1, index=0, start_minute=480, week_index=0)
    classroom = room(1, "611", 30)
    session = occurrence(1, start(time_slot), classroom, demand=80)
    session = replace(
        session,
        compatible_room_ids=frozenset(),
        allowed_start_room_pairs=frozenset(),
    )
    data = scheduling_input(
        slots=(time_slot,),
        rooms=(classroom,),
        occurrences=(session,),
    )

    assert "NO_COMPATIBLE_ROOM" in _issue_codes(data)


def test_staff_without_a_free_window_produces_no_feasible_start() -> None:
    time_slot = slot(
        1,
        day=1,
        index=0,
        start_minute=480,
        week_index=0,
    )
    classroom = room(1, "611", 100)
    session = occurrence(
        1,
        start(time_slot),
        classroom,
        staff_id=10,
    )

    # Staff availability does not produce any feasible start candidate.
    session = replace(
        session,
        start_candidates=(),
        allowed_start_room_pairs=frozenset(),
    )

    data = scheduling_input(
        slots=(time_slot,),
        rooms=(classroom,),
        occurrences=(session,),
    )

    assert "NO_FEASIBLE_START" in _issue_codes(data)

def test_contradictory_fixed_windows_produce_no_feasible_start() -> None:
    time_slot = slot(1, day=1, index=0, start_minute=480, week_index=0)
    classroom = room(1, "611", 100)
    session = occurrence(1, start(time_slot), classroom)
    session = replace(
        session,
        time_constraints=(
            SessionTimeConstraint(
                day_of_week=1,
                start_minute=480,
                end_minute=525,
                constraint_type=TimeConstraintType.FIXED_WINDOW,
            ),
            SessionTimeConstraint(
                day_of_week=1,
                start_minute=525,
                end_minute=570,
                constraint_type=TimeConstraintType.FIXED_WINDOW,
            ),
        ),
        start_candidates=(),
        allowed_start_room_pairs=frozenset(),
    )
    data = scheduling_input(
        slots=(time_slot,),
        rooms=(classroom,),
        occurrences=(session,),
    )

    assert "NO_FEASIBLE_START" in _issue_codes(data)


def test_cyclic_session_dependencies_are_rejected() -> None:
    first_slot = slot(1, day=1, index=0, start_minute=480, week_index=0)
    second_slot = slot(2, day=1, index=1, start_minute=525, week_index=1)
    classroom = room(1, "611", 100)
    first = occurrence(1, start(first_slot), classroom, staff_id=1)
    second = occurrence(2, start(second_slot), classroom, staff_id=2)
    data = scheduling_input(
        slots=(first_slot, second_slot),
        rooms=(classroom,),
        occurrences=(first, second),
        dependencies=(
            SessionDependency(1, 1, 2, DependencyType.PRECEDES),
            SessionDependency(2, 2, 1, DependencyType.PRECEDES),
        ),
    )

    assert "DEPENDENCY_CYCLE" in _issue_codes(data)


def test_two_sessions_using_the_same_room_and_slot_are_rejected() -> None:
    time_slot = slot(1, day=1, index=0, start_minute=480, week_index=0)
    classroom = room(1, "611", 100)
    first = occurrence(1, start(time_slot), classroom, staff_id=1)
    second = occurrence(2, start(time_slot), classroom, staff_id=2)
    data = scheduling_input(
        slots=(time_slot,),
        rooms=(classroom,),
        occurrences=(first, second),
    )
    assignments = (
        SolverAssignment(1, 1, classroom.id, time_slot.id),
        SolverAssignment(2, 1, classroom.id, time_slot.id),
    )

    result = validate_solver_result(data, assignments)

    assert "ROOM_OVERLAP" in {issue.code for issue in result.issues}


def test_locked_entry_conflicting_with_another_locked_entry_is_rejected() -> None:
    time_slot = slot(1, day=1, index=0, start_minute=480, week_index=0)
    classroom = room(1, "611", 100)
    first = occurrence(1, start(time_slot), classroom, staff_id=1)
    second = occurrence(2, start(time_slot), classroom, staff_id=2)
    data = scheduling_input(
        slots=(time_slot,),
        rooms=(classroom,),
        occurrences=(first, second),
        locked_assignments=(
            LockedAssignment(1, 1, classroom.id, time_slot.id),
            LockedAssignment(2, 1, classroom.id, time_slot.id),
        ),
    )

    assert "LOCKED_ROOM_OVERLAP" in _issue_codes(data)


def test_greedy_solver_reports_infeasible_locked_conflict() -> None:
    time_slot = slot(1, day=1, index=0, start_minute=480, week_index=0)
    classroom = room(1, "611", 100)
    first = occurrence(1, start(time_slot), classroom, staff_id=1)
    second = occurrence(2, start(time_slot), classroom, staff_id=2)
    data = scheduling_input(
        slots=(time_slot,),
        rooms=(classroom,),
        occurrences=(first, second),
        locked_assignments=(LockedAssignment(1, 1, classroom.id, time_slot.id),),
    )

    result = GreedyTimetableSolver(RoomStrategy.BFD).solve(data)

    assert result.status == TimetableRunStatus.FAILED
    assert result.diagnostics["reason"] == "greedy_search_exhausted"
