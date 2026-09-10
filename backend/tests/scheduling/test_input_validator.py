from app.scheduling.domain import LockedAssignment
from app.scheduling.input_validator import validate_scheduling_input
from tests.scheduling.factories import occurrence, room, scheduling_input, slot, start


def test_conflicting_locked_rooms_are_rejected_before_solving() -> None:
    time_slot = slot(1, day=1, index=0, start_minute=480, week_index=0)
    classroom = room(1, "611", 100)
    candidate = start(time_slot)
    first = occurrence(1, candidate, classroom, staff_id=1)
    second = occurrence(2, candidate, classroom, staff_id=2)
    data = scheduling_input(
        slots=(time_slot,),
        rooms=(classroom,),
        occurrences=(first, second),
        locked_assignments=(
            LockedAssignment(1, 1, classroom.id, time_slot.id),
            LockedAssignment(2, 1, classroom.id, time_slot.id),
        ),
    )

    result = validate_scheduling_input(data)

    assert "LOCKED_ROOM_OVERLAP" in {issue.code for issue in result.issues}


def test_invalid_master_evening_window_is_rejected() -> None:
    time_slot = slot(1, day=1, index=0, start_minute=480, week_index=0)
    classroom = room(1, "611", 100)
    session = occurrence(1, start(time_slot), classroom)
    data = scheduling_input(
        slots=(time_slot,),
        rooms=(classroom,),
        occurrences=(session,),
        parameters={
            "master_evening_start_minute": 20 * 60,
            "master_evening_end_minute": 17 * 60,
        },
    )

    result = validate_scheduling_input(data)

    assert "INVALID_SOLVER_PARAMETER" in {issue.code for issue in result.issues}


def test_zero_solver_time_limit_means_no_limit() -> None:
    time_slot = slot(1, day=1, index=0, start_minute=480, week_index=0)
    classroom = room(1, "611", 100)
    session = occurrence(1, start(time_slot), classroom)
    data = scheduling_input(
        slots=(time_slot,),
        rooms=(classroom,),
        occurrences=(session,),
        parameters={"time_limit_seconds": 0},
    )

    result = validate_scheduling_input(data)

    assert result.is_valid
