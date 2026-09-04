from app.core.exceptions import BusinessRuleError
from app.models.enums import TimetableRunStatus
from app.models.timetable_run import TimetableRun
from app.services.common import commit_and_refresh, require_active, require_by_id
from app.services.timetable.validation import validate_timetable_run
from sqlalchemy import select
from sqlalchemy.orm import Session


def publish_timetable_run(
    db: Session,
    timetable_run_id: int,
) -> TimetableRun:
    run = require_by_id(db, TimetableRun, timetable_run_id, "Timetable run")
    locked_runs = tuple(
        db.scalars(
            select(TimetableRun)
            .where(
                TimetableRun.academic_term_id == run.academic_term_id,
                TimetableRun.scheduling_profile_id == run.scheduling_profile_id,
            )
            .with_for_update()
        ).all()
    )
    run = next(item for item in locked_runs if item.id == timetable_run_id)
    if run.status != TimetableRunStatus.SUCCEEDED:
        raise BusinessRuleError(
            "Only a SUCCEEDED timetable run can be published.",
            details={"timetable_run_id": run.id, "status": run.status},
        )
    require_active(run.academic_term, "Academic term")
    require_active(run.scheduling_profile, "Scheduling profile")
    validation = validate_timetable_run(db, run.id)
    run.hard_conflicts = validation.hard_conflict_count
    if not validation.is_valid:
        raise BusinessRuleError(
            "A timetable can only be published with zero hard conflicts.",
            details={
                "timetable_run_id": run.id,
                "hard_conflicts": validation.hard_conflict_count,
                "conflict_codes": sorted({item.code for item in validation.hard_conflicts}),
            },
        )
    for other_run in locked_runs:
        other_run.is_published = other_run.id == run.id
    return commit_and_refresh(db, run)


def unpublish_timetable_run(
    db: Session,
    timetable_run_id: int,
) -> TimetableRun:
    run = require_by_id(db, TimetableRun, timetable_run_id, "Timetable run")
    db.scalar(select(TimetableRun.id).where(TimetableRun.id == run.id).with_for_update())
    run.is_published = False
    return commit_and_refresh(db, run)
