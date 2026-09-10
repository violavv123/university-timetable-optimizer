from dataclasses import replace

import app.scheduling.cp_sat_solver as cp_sat_solver
from app.models.enums import TimetableRunStatus
from app.scheduling.cp_sat_solver import CpSatTimetableSolver, HybridTimetableSolver
from tests.scheduling.factories import occurrence, room, scheduling_input, slot, start


def test_cp_sat_finds_and_independently_validates_feasible_schedule() -> None:
    time_slot = slot(1, day=1, index=0, start_minute=480, week_index=0)
    classroom = room(1, "611", 100)
    session = occurrence(1, start(time_slot), classroom)
    data = scheduling_input(
        slots=(time_slot,),
        rooms=(classroom,),
        occurrences=(session,),
        parameters={"time_limit_seconds": 2.0, "num_search_workers": 1},
    )

    result = CpSatTimetableSolver().solve(data)

    assert result.status == TimetableRunStatus.SUCCEEDED
    assert len(result.assignments) == 1
    assert result.diagnostics["cp_sat_status"] == "OPTIMAL"


def test_cp_sat_can_prove_resource_infeasibility() -> None:
    time_slot = slot(1, day=1, index=0, start_minute=480, week_index=0)
    classroom = room(1, "611", 100)
    candidate = start(time_slot)
    first = occurrence(1, candidate, classroom, staff_id=1)
    second = occurrence(2, candidate, classroom, staff_id=2)
    data = scheduling_input(
        slots=(time_slot,),
        rooms=(classroom,),
        occurrences=(first, second),
        parameters={"time_limit_seconds": 2.0, "num_search_workers": 1},
    )

    result = CpSatTimetableSolver().solve(data)

    assert result.status == TimetableRunStatus.INFEASIBLE


def test_hybrid_continues_without_a_complete_greedy_hint() -> None:
    first_slot = slot(1, day=1, index=0, start_minute=480, week_index=0)
    second_slot = slot(2, day=1, index=1, start_minute=525, week_index=1)
    classroom = room(1, "611", 100)
    first_start = start(first_slot)
    second_start = start(second_slot)
    flexible = occurrence(1, first_start, classroom, demand=80, staff_id=1)
    flexible = replace(
        flexible,
        start_candidates=(first_start, second_start),
        allowed_start_room_pairs=frozenset(
            {
                (first_slot.id, classroom.id),
                (second_slot.id, classroom.id),
            }
        ),
    )
    constrained = occurrence(2, first_start, classroom, demand=30, staff_id=2)
    data = scheduling_input(
        slots=(first_slot, second_slot),
        rooms=(classroom,),
        occurrences=(flexible, constrained),
        parameters={"time_limit_seconds": 2.0, "num_search_workers": 1},
    )

    result = HybridTimetableSolver().solve(data)

    assert result.status == TimetableRunStatus.SUCCEEDED
    assert result.diagnostics["greedy_hint_count"] == 0


def test_large_cp_sat_and_hybrid_return_one_validated_baseline(monkeypatch) -> None:
    time_slot = slot(1, day=1, index=0, start_minute=480, week_index=0)
    classroom = room(1, "611", 100)
    session = occurrence(1, start(time_slot), classroom)
    data = scheduling_input(
        slots=(time_slot,),
        rooms=(classroom,),
        occurrences=(session,),
        parameters={"time_limit_seconds": 8.0, "num_search_workers": 2},
    )
    monkeypatch.setattr(cp_sat_solver, "FAST_PATH_OCCURRENCE_COUNT", 1)

    for solver in (CpSatTimetableSolver(), HybridTimetableSolver()):
        result = solver.solve(data)

        assert result.status == TimetableRunStatus.SUCCEEDED
        assert len(result.assignments) == 1
        assert "baseline" in result.diagnostics["fast_path"]
