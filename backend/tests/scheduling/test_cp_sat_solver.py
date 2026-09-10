from dataclasses import replace

import app.scheduling.cp_sat_solver as cp_sat_solver
from app.models.enums import TimetableRunStatus
from app.scheduling.cp_sat_solver import CpSatTimetableSolver, HybridTimetableSolver
from app.scheduling.domain import SolverResult
from app.schemas.scheduler import SchedulingParameters
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
    assert result.diagnostics["cp_sat_status"] in {"FEASIBLE", "OPTIMAL"}


def test_scheduler_accepts_unlimited_solver_time() -> None:
    assert SchedulingParameters().time_limit_seconds == 0
    assert SchedulingParameters(time_limit_seconds=45).time_limit_seconds == 45


def test_unlimited_cp_sat_returns_first_solution_without_optimizing(monkeypatch) -> None:
    time_slot = slot(1, day=1, index=0, start_minute=480, week_index=0)
    classroom = room(1, "611", 100)
    session = occurrence(1, start(time_slot), classroom)
    data = scheduling_input(
        slots=(time_slot,),
        rooms=(classroom,),
        occurrences=(session,),
        parameters={"time_limit_seconds": 0.0, "num_search_workers": 1},
    )
    minimize_calls: list[object] = []
    monkeypatch.setattr(
        cp_sat_solver.cp_model.CpModel,
        "minimize",
        lambda _model, expression: minimize_calls.append(expression),
    )

    result = CpSatTimetableSolver().solve(data)

    assert result.status == TimetableRunStatus.SUCCEEDED
    assert minimize_calls == []


def test_cp_sat_cancel_request_stops_the_result() -> None:
    time_slot = slot(1, day=1, index=0, start_minute=480, week_index=0)
    classroom = room(1, "611", 100)
    session = occurrence(1, start(time_slot), classroom)
    data = scheduling_input(
        slots=(time_slot,),
        rooms=(classroom,),
        occurrences=(session,),
        parameters={"time_limit_seconds": 0.0, "num_search_workers": 1},
    )
    solver = CpSatTimetableSolver()
    solver.cancel()

    result = solver.solve(data)

    assert result.status == TimetableRunStatus.FAILED
    assert result.diagnostics["message"] == "CP-SAT search was cancelled."


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


def test_oversized_input_does_not_build_unbounded_cp_sat_model(monkeypatch) -> None:
    time_slot = slot(1, day=1, index=0, start_minute=480, week_index=0)
    classroom = room(1, "611", 100)
    data = scheduling_input(
        slots=(time_slot,),
        rooms=(classroom,),
        occurrences=(occurrence(1, start(time_slot), classroom),),
    )

    def failed_baseline(*_: object, **__: object) -> SolverResult:
        return SolverResult(
            status=TimetableRunStatus.FAILED,
            diagnostics={"reason": "greedy_search_exhausted"},
        )

    def model_must_not_be_built() -> object:
        raise AssertionError("oversized inputs must not build a CP-SAT model")

    monkeypatch.setattr(cp_sat_solver, "MAX_ALLOWED_PAIRS_FOR_CP_SAT", 0)
    monkeypatch.setattr(cp_sat_solver.GreedyTimetableSolver, "solve", failed_baseline)
    monkeypatch.setattr(cp_sat_solver.cp_model, "CpModel", model_must_not_be_built)

    result = CpSatTimetableSolver().solve(data)

    assert result.status == TimetableRunStatus.FAILED
    assert result.diagnostics["reason"] == "fast_baseline_exhausted"
