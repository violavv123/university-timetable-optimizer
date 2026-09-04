from typing import Protocol

from app.core.exceptions import BusinessRuleError
from app.models.enums import TimetableRunStatus, TimetableSourceType
from app.models.timetable_run import TimetableRun
from app.services.common import commit_and_refresh
from app.services.timetable.timetable_entry import persist_solver_assignments
from app.services.timetable.timetable_run import (
    complete_timetable_run,
    get_timetable_run,
    start_timetable_run,
)
from app.services.timetable.types import SolverOutcome
from sqlalchemy.orm import Session


class TimetableSolver(Protocol):
    def __call__(
        self,
        db: Session,
        run: TimetableRun,
    ) -> SolverOutcome: ...


def generate_timetable(
    db: Session,
    timetable_run_id: int,
    solver: TimetableSolver,
) -> TimetableRun:
    run = get_timetable_run(db, timetable_run_id)
    if run.source_type not in {
        TimetableSourceType.GENERATED,
        TimetableSourceType.REOPTIMIZED,
    }:
        raise BusinessRuleError("Only generated or reoptimized runs can invoke the solver.")
    run = start_timetable_run(db, run.id)
    try:
        outcome = solver(db, run)
        if outcome.status == TimetableRunStatus.INFEASIBLE:
            return complete_timetable_run(
                db,
                run.id,
                status=TimetableRunStatus.INFEASIBLE,
                objective_score=outcome.objective_score,
                soft_penalty=outcome.soft_penalty,
                execution_time_ms=outcome.execution_time_ms,
            )
        if outcome.status != TimetableRunStatus.SUCCEEDED:
            raise BusinessRuleError(
                "The solver must return SUCCEEDED or INFEASIBLE.",
                details={"solver_status": outcome.status},
            )
        persist_solver_assignments(
            db,
            run.id,
            outcome.assignments,
            preserve_locked=(run.source_type == TimetableSourceType.REOPTIMIZED),
        )
        return complete_timetable_run(
            db,
            run.id,
            status=TimetableRunStatus.SUCCEEDED,
            objective_score=outcome.objective_score,
            soft_penalty=outcome.soft_penalty,
            execution_time_ms=outcome.execution_time_ms,
        )
    except Exception:
        db.rollback()
        failed_run = get_timetable_run(db, run.id)
        if failed_run.status == TimetableRunStatus.RUNNING:
            failed_run.status = TimetableRunStatus.FAILED
            commit_and_refresh(db, failed_run)
        raise
