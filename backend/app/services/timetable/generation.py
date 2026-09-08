from typing import Protocol

from app.core.exceptions import BusinessRuleError
from app.models.enums import AssignmentSource, TimetableRunStatus, TimetableSourceType
from app.models.timetable_run import TimetableRun
from app.scheduling.domain import SolverAssignment
from app.scheduling.input_loader import load_scheduling_input
from app.scheduling.input_validator import require_valid_scheduling_input
from app.scheduling.result_validator import require_valid_solver_result
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
        scheduling_input = load_scheduling_input(db, run)
        require_valid_scheduling_input(scheduling_input)
        complete_assignments = tuple(
            SolverAssignment(
                course_session_id=locked.course_session_id,
                occurrence_number=locked.occurrence_number,
                room_id=locked.room_id,
                start_slot_id=locked.start_slot_id,
                is_locked=True,
                assignment_source=AssignmentSource.PRESERVED,
            )
            for locked in scheduling_input.locked_assignments
        ) + tuple(
            SolverAssignment(
                course_session_id=assignment.course_session_id,
                occurrence_number=assignment.occurrence_number,
                room_id=assignment.room_id,
                start_slot_id=assignment.start_slot_id,
            )
            for assignment in outcome.assignments
        )
        # This validator does not trust the solver model. It checks the complete
        # result independently before any generated row is persisted.
        require_valid_solver_result(scheduling_input, complete_assignments)
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
