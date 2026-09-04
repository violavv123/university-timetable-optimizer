from app.core.exceptions import BusinessRuleError
from app.models.enums import (
    AssignmentSource,
    TimetableRunStatus,
    TimetableSourceType,
)
from app.models.timetable_entry import TimetableEntry
from app.models.timetable_run import TimetableRun
from app.schemas.timetable_run import TimetableRunCreate
from app.services.common import (
    commit_and_refresh,
    commit_transaction,
    flush_transaction,
    require_by_id,
)
from app.services.timetable.generation import TimetableSolver, generate_timetable
from app.services.timetable.timetable_run import create_timetable_run
from app.services.timetable.validation import (
    collect_entry_conflicts,
    validate_timetable_run,
)
from sqlalchemy import select
from sqlalchemy.orm import Session


def prepare_reoptimized_run(
    db: Session,
    source_run_id: int,
    payload: TimetableRunCreate,
) -> TimetableRun:
    source_run = require_by_id(
        db,
        TimetableRun,
        source_run_id,
        "Source timetable run",
    )
    if source_run.status != TimetableRunStatus.SUCCEEDED:
        raise BusinessRuleError("Only a SUCCEEDED run can be used for reoptimization.")
    if payload.source_type != TimetableSourceType.REOPTIMIZED:
        raise BusinessRuleError("The new run must use source_type=REOPTIMIZED.")
    if payload.parameters.get("source_run_id") != source_run.id:
        raise BusinessRuleError("parameters.source_run_id must match the selected source run.")
    source_validation = validate_timetable_run(db, source_run.id)
    if not source_validation.is_valid:
        raise BusinessRuleError(
            "The source run must pass current validation before reoptimization.",
            details={
                "source_run_id": source_run.id,
                "hard_conflicts": source_validation.hard_conflict_count,
            },
        )
    new_run = create_timetable_run(db, payload)
    locked_entries = tuple(
        db.scalars(
            select(TimetableEntry).where(
                TimetableEntry.timetable_run_id == source_run.id,
                TimetableEntry.is_locked.is_(True),
            )
        ).all()
    )
    try:
        for source_entry in locked_entries:
            conflicts = collect_entry_conflicts(
                db,
                timetable_run_id=new_run.id,
                course_session_id=source_entry.course_session_id,
                occurrence_number=source_entry.occurrence_number,
                room_id=source_entry.room_id,
                start_slot_id=source_entry.start_slot_id,
            )
            if conflicts:
                first = conflicts[0]
                raise BusinessRuleError(
                    "A locked source entry is no longer valid for reoptimization.",
                    details={
                        "source_entry_id": source_entry.id,
                        "conflict_code": first.code,
                        **first.details,
                    },
                )
            preserved = TimetableEntry(
                timetable_run_id=new_run.id,
                course_session_id=source_entry.course_session_id,
                occurrence_number=source_entry.occurrence_number,
                room_id=source_entry.room_id,
                start_slot_id=source_entry.start_slot_id,
                is_locked=True,
                assignment_source=AssignmentSource.PRESERVED,
            )
            db.add(preserved)
            flush_transaction(db)
        commit_transaction(db)
    except Exception:
        db.rollback()
        failed_run = require_by_id(
            db,
            TimetableRun,
            new_run.id,
            "Reoptimized timetable run",
        )
        failed_run.status = TimetableRunStatus.FAILED
        failed_run.hard_conflicts = 1
        commit_and_refresh(db, failed_run)
        raise
    db.refresh(new_run)
    return new_run


def reoptimize_timetable(
    db: Session,
    source_run_id: int,
    payload: TimetableRunCreate,
    solver: TimetableSolver,
) -> TimetableRun:
    run = prepare_reoptimized_run(db, source_run_id, payload)
    return generate_timetable(db, run.id, solver)
