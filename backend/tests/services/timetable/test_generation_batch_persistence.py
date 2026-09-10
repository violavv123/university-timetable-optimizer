from types import SimpleNamespace

import app.services.timetable.generation as generation_service
from app.models.enums import TimetableRunStatus, TimetableSourceType
from app.services.timetable.types import SolverOutcome, TimetableAssignment


def test_successful_generation_uses_validated_batch_persistence(
    monkeypatch,
) -> None:
    run = SimpleNamespace(
        id=7,
        source_type=TimetableSourceType.GENERATED,
    )
    outcome = SolverOutcome(
        status=TimetableRunStatus.SUCCEEDED,
        assignments=(
            TimetableAssignment(
                course_session_id=11,
                occurrence_number=1,
                room_id=21,
                start_slot_id=31,
            ),
        ),
    )
    calls: dict[str, object] = {}

    monkeypatch.setattr(generation_service, "get_timetable_run", lambda db, run_id: run)
    monkeypatch.setattr(generation_service, "start_timetable_run", lambda db, run_id: run)
    monkeypatch.setattr(
        generation_service,
        "load_scheduling_input",
        lambda db, current_run: SimpleNamespace(locked_assignments=()),
    )
    monkeypatch.setattr(
        generation_service,
        "require_valid_scheduling_input",
        lambda scheduling_input: None,
    )
    monkeypatch.setattr(
        generation_service,
        "require_valid_solver_result",
        lambda scheduling_input, assignments: calls.update(
            solver_validation=True,
        ),
    )
    monkeypatch.setattr(
        generation_service,
        "persist_solver_assignments",
        lambda db, run_id, assignments, **kwargs: calls.update(
            persist=kwargs,
        ),
    )
    monkeypatch.setattr(
        generation_service,
        "complete_timetable_run",
        lambda db, run_id, **kwargs: calls.update(complete=kwargs) or run,
    )

    result = generation_service.generate_timetable(
        object(),
        run.id,
        lambda db, current_run: outcome,
    )

    assert result is run
    assert calls["solver_validation"] is True
    assert calls["persist"] == {
        "preserve_locked": False,
        "validate_assignments": False,
    }
    assert calls["complete"] == {
        "status": TimetableRunStatus.SUCCEEDED,
        "objective_score": None,
        "soft_penalty": None,
        "execution_time_ms": None,
        "validate": False,
    }
