import pytest
from app.core.exceptions import BusinessRuleError
from app.models.enums import (
    AssignmentSource,
    SchedulingAlgorithm,
    TimetableRunStatus,
    TimetableSourceType,
)
from app.models.timetable_entry import TimetableEntry
from app.schemas.timetable_run import TimetableRunCreate
from app.services.timetable.generation import generate_timetable
from app.services.timetable.reoptimization import prepare_reoptimized_run
from app.services.timetable.timetable_entry import set_timetable_entry_lock
from app.services.timetable.types import SolverOutcome
from sqlalchemy import select
from sqlalchemy.orm import Session
from tests.services.timetable.factories import (
    complete_valid_manual_run,
    make_manual_entry,
    make_ready_timetable_context,
)

pytestmark = pytest.mark.integration


def test_generated_run_rejects_manual_entry_writes(db: Session) -> None:
    context = make_ready_timetable_context(
        db,
        source_type=TimetableSourceType.GENERATED,
    )

    with pytest.raises(BusinessRuleError, match="persisted by the generation"):
        make_manual_entry(db, context)


def test_solver_contract_failure_marks_run_failed(db: Session) -> None:
    context = make_ready_timetable_context(
        db,
        source_type=TimetableSourceType.GENERATED,
    )

    def invalid_solver(*_: object) -> SolverOutcome:
        return SolverOutcome(status=TimetableRunStatus.FAILED)

    with pytest.raises(BusinessRuleError, match="SUCCEEDED or INFEASIBLE"):
        generate_timetable(db, context.run.id, invalid_solver)

    db.refresh(context.run)
    assert context.run.status == TimetableRunStatus.FAILED


def test_reoptimization_preserves_locked_source_entries(db: Session) -> None:
    context = make_ready_timetable_context(db)
    source_entry = make_manual_entry(db, context)
    complete_valid_manual_run(db, context)
    set_timetable_entry_lock(db, source_entry.id, is_locked=True)
    payload = TimetableRunCreate(
        academic_term_id=context.scheduling.resources.academic_term.id,
        scheduling_profile_id=context.scheduling.profile.id,
        name="Reoptimized run",
        source_type=TimetableSourceType.REOPTIMIZED,
        algorithm=SchedulingAlgorithm.CP_SAT,
        parameters={"source_run_id": context.run.id},
    )

    reoptimized = prepare_reoptimized_run(db, context.run.id, payload)
    preserved = db.scalar(
        select(TimetableEntry).where(TimetableEntry.timetable_run_id == reoptimized.id)
    )

    assert preserved is not None
    assert preserved.course_session_id == source_entry.course_session_id
    assert preserved.start_slot_id == source_entry.start_slot_id
    assert preserved.is_locked is True
    assert preserved.assignment_source == AssignmentSource.PRESERVED
