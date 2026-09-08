from app.models.enums import DependencyType, TimetableRunStatus
from app.scheduling.domain import RoomStrategy, SessionDependency
from app.scheduling.greedy_solver import GreedyTimetableSolver
from tests.scheduling.factories import occurrence, room, scheduling_input, slot, start


def test_greedy_exhaustion_is_not_reported_as_proven_infeasible() -> None:
    time_slot = slot(1, day=1, index=0, start_minute=480, week_index=0)
    classroom = room(1, "611", 100)
    candidate = start(time_slot)
    first = occurrence(1, candidate, classroom, staff_id=1)
    second = occurrence(2, candidate, classroom, staff_id=2)
    data = scheduling_input(
        slots=(time_slot,),
        rooms=(classroom,),
        occurrences=(first, second),
    )

    result = GreedyTimetableSolver(RoomStrategy.BFD).solve(data)

    assert result.status == TimetableRunStatus.FAILED
    assert result.diagnostics["reason"] == "greedy_search_exhausted"


def test_same_day_successor_may_be_considered_before_predecessor() -> None:
    first_slot = slot(1, day=1, index=0, start_minute=480, week_index=0)
    second_slot = slot(2, day=1, index=1, start_minute=525, week_index=1)
    room_611 = room(1, "611", 100)
    room_621 = room(2, "621", 100)
    predecessor = occurrence(1, start(second_slot), room_621, demand=20)
    successor = occurrence(2, start(first_slot), room_611, demand=80)
    same_day = SessionDependency(
        id=1,
        predecessor_session_id=1,
        successor_session_id=2,
        dependency_type=DependencyType.SAME_DAY,
    )
    data = scheduling_input(
        slots=(first_slot, second_slot),
        rooms=(room_611, room_621),
        occurrences=(predecessor, successor),
        dependencies=(same_day,),
    )

    result = GreedyTimetableSolver(RoomStrategy.BFD).solve(data)

    assert result.status == TimetableRunStatus.SUCCEEDED
