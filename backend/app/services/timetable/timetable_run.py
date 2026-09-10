import json
from decimal import Decimal

from app.core.exceptions import BusinessRuleError, ResourceInUseError
from app.models.academic_term import AcademicTerm
from app.models.enums import (
    TimetableRunStatus,
    TimetableSourceType,
)
from app.models.scheduling_profile import SchedulingProfile
from app.models.time_slot import TimeSlot
from app.models.timetable_entry import TimetableEntry
from app.models.timetable_run import TimetableRun
from app.schemas.common import MessageResponse, PaginatedResponse, PaginationParams
from app.schemas.timetable_run import (
    TimetableRunCreate,
    TimetableRunRead,
    TimetableRunUpdate,
)
from app.services.common import (
    apply_changes,
    commit_and_refresh,
    commit_delete,
    ensure_unique,
    paginated_rows,
    require_active,
    require_by_id,
    validated_changes,
)
from app.services.timetable.validation import validate_timetable_run
from sqlalchemy import func, select
from sqlalchemy.orm import Session


def _normalized_name(name: str) -> str:
    normalized = " ".join(name.split())
    if not normalized:
        raise BusinessRuleError("name cannot be blank.")
    return normalized


def _validate_parameters(parameters: object) -> dict[str, object]:
    if not isinstance(parameters, dict):
        raise BusinessRuleError("parameters must be a JSON object.")
    try:
        json.dumps(parameters)
    except (TypeError, ValueError) as error:
        raise BusinessRuleError("parameters must contain JSON-serializable values.") from error
    return parameters


def _validate_source_configuration(
    db: Session,
    *,
    academic_term_id: int,
    scheduling_profile_id: int,
    source_type: TimetableSourceType,
    algorithm: object | None,
    parameters: dict[str, object],
) -> None:
    if (
        source_type
        in {
            TimetableSourceType.GENERATED,
            TimetableSourceType.REOPTIMIZED,
        }
        and algorithm is None
    ):
        raise BusinessRuleError("Generated and reoptimized runs require a scheduling algorithm.")
    if source_type != TimetableSourceType.REOPTIMIZED:
        return
    source_run_id = parameters.get("source_run_id")
    if isinstance(source_run_id, bool) or not isinstance(source_run_id, int):
        raise BusinessRuleError("A reoptimized run requires integer parameters.source_run_id.")
    source_run = require_by_id(
        db,
        TimetableRun,
        source_run_id,
        "Source timetable run",
    )
    if source_run.status != TimetableRunStatus.SUCCEEDED:
        raise BusinessRuleError(
            "Only a successful timetable run can be reoptimized.",
            details={
                "source_run_id": source_run.id,
                "source_run_status": source_run.status,
            },
        )
    if (
        source_run.academic_term_id != academic_term_id
        or source_run.scheduling_profile_id != scheduling_profile_id
    ):
        raise BusinessRuleError(
            "A reoptimized run must keep its source term and profile.",
            details={"source_run_id": source_run.id},
        )


def _validate_parents(
    db: Session,
    *,
    academic_term_id: int,
    scheduling_profile_id: int,
) -> None:
    term = require_by_id(db, AcademicTerm, academic_term_id, "Academic term")
    profile = require_by_id(
        db,
        SchedulingProfile,
        scheduling_profile_id,
        "Scheduling profile",
    )
    require_active(term, "Academic term")
    require_active(profile, "Scheduling profile")
    active_slot_id = db.scalar(
        select(TimeSlot.id)
        .where(
            TimeSlot.scheduling_profile_id == profile.id,
            TimeSlot.is_active.is_(True),
        )
        .limit(1)
    )
    if active_slot_id is None:
        raise BusinessRuleError(
            "A timetable run requires a profile with active time slots.",
            details={"scheduling_profile_id": profile.id},
        )


def get_timetable_run(db: Session, timetable_run_id: int) -> TimetableRun:
    return require_by_id(db, TimetableRun, timetable_run_id, "Timetable run")


def list_timetable_runs(
    db: Session,
    pagination: PaginationParams,
    *,
    academic_term_id: int | None = None,
    scheduling_profile_id: int | None = None,
    status: TimetableRunStatus | None = None,
    is_published: bool | None = None,
) -> PaginatedResponse[TimetableRunRead]:
    filters = []
    if academic_term_id is not None:
        require_by_id(db, AcademicTerm, academic_term_id, "Academic term")
        filters.append(TimetableRun.academic_term_id == academic_term_id)
    if scheduling_profile_id is not None:
        require_by_id(
            db,
            SchedulingProfile,
            scheduling_profile_id,
            "Scheduling profile",
        )
        filters.append(TimetableRun.scheduling_profile_id == scheduling_profile_id)
    if status is not None:
        filters.append(TimetableRun.status == status)
    if is_published is not None:
        filters.append(TimetableRun.is_published.is_(is_published))
    statement = (
        select(TimetableRun)
        .where(*filters)
        .order_by(TimetableRun.created_at.desc(), TimetableRun.id.desc())
    )
    count_statement = select(func.count()).select_from(TimetableRun).where(*filters)
    rows, total = paginated_rows(db, statement, count_statement, pagination)
    return PaginatedResponse[TimetableRunRead](
        items=[TimetableRunRead.model_validate(row) for row in rows],
        total=total,
        page=pagination.page,
        page_size=pagination.page_size,
    )


def create_timetable_run(
    db: Session,
    payload: TimetableRunCreate,
) -> TimetableRun:
    name = _normalized_name(payload.name)
    parameters = _validate_parameters(payload.parameters)
    _validate_parents(
        db,
        academic_term_id=payload.academic_term_id,
        scheduling_profile_id=payload.scheduling_profile_id,
    )
    _validate_source_configuration(
        db,
        academic_term_id=payload.academic_term_id,
        scheduling_profile_id=payload.scheduling_profile_id,
        source_type=payload.source_type,
        algorithm=payload.algorithm,
        parameters=parameters,
    )
    ensure_unique(
        db,
        TimetableRun,
        "Timetable run",
        ["academic_term_id", "scheduling_profile_id", "name"],
        TimetableRun.academic_term_id == payload.academic_term_id,
        TimetableRun.scheduling_profile_id == payload.scheduling_profile_id,
        func.lower(TimetableRun.name) == name.lower(),
    )
    run = TimetableRun(
        academic_term_id=payload.academic_term_id,
        scheduling_profile_id=payload.scheduling_profile_id,
        name=name,
        source_type=payload.source_type,
        algorithm=payload.algorithm,
        status=TimetableRunStatus.PENDING,
        parameters=parameters,
        objective_score=None,
        hard_conflicts=0,
        soft_penalty=None,
        execution_time_ms=None,
        is_published=False,
    )
    db.add(run)
    return commit_and_refresh(db, run)


def update_timetable_run(
    db: Session,
    timetable_run_id: int,
    payload: TimetableRunUpdate,
) -> TimetableRun:
    run = get_timetable_run(db, timetable_run_id)
    if run.status != TimetableRunStatus.PENDING or run.is_published:
        raise ResourceInUseError(
            "Only an unpublished PENDING run can be edited.",
            details={"timetable_run_id": run.id, "status": run.status},
        )
    if (
        db.scalar(
            select(TimetableEntry.id).where(TimetableEntry.timetable_run_id == run.id).limit(1)
        )
        is not None
    ):
        raise ResourceInUseError(
            "A run with entries cannot change its configuration.",
            details={"timetable_run_id": run.id},
        )
    changes = validated_changes(payload)
    prohibited = set(changes).difference({"name", "algorithm", "parameters"})
    if prohibited:
        raise BusinessRuleError(
            "Run parents, source, status, metrics, and publication are managed "
            "by dedicated workflow operations.",
            details={"prohibited_fields": sorted(prohibited)},
        )
    if "name" in changes:
        changes["name"] = _normalized_name(changes["name"])
    if "parameters" in changes:
        changes["parameters"] = _validate_parameters(changes["parameters"])
    algorithm = changes.get("algorithm", run.algorithm)
    parameters = changes.get("parameters", run.parameters)
    _validate_source_configuration(
        db,
        academic_term_id=run.academic_term_id,
        scheduling_profile_id=run.scheduling_profile_id,
        source_type=run.source_type,
        algorithm=algorithm,
        parameters=parameters,
    )
    name = changes.get("name", run.name)
    ensure_unique(
        db,
        TimetableRun,
        "Timetable run",
        ["academic_term_id", "scheduling_profile_id", "name"],
        TimetableRun.academic_term_id == run.academic_term_id,
        TimetableRun.scheduling_profile_id == run.scheduling_profile_id,
        func.lower(TimetableRun.name) == name.lower(),
        exclude_id=run.id,
    )
    apply_changes(run, changes)
    return commit_and_refresh(db, run)


def start_timetable_run(db: Session, timetable_run_id: int) -> TimetableRun:
    run = get_timetable_run(db, timetable_run_id)
    if run.status != TimetableRunStatus.PENDING:
        raise BusinessRuleError(
            "Only a PENDING timetable run can start.",
            details={"timetable_run_id": run.id, "status": run.status},
        )
    _validate_parents(
        db,
        academic_term_id=run.academic_term_id,
        scheduling_profile_id=run.scheduling_profile_id,
    )
    run.status = TimetableRunStatus.RUNNING
    return commit_and_refresh(db, run)


def complete_timetable_run(
    db: Session,
    timetable_run_id: int,
    *,
    status: TimetableRunStatus,
    objective_score: Decimal | None = None,
    soft_penalty: Decimal | None = None,
    execution_time_ms: int | None = None,
    validate: bool = True,
) -> TimetableRun:
    run = get_timetable_run(db, timetable_run_id)
    if run.status != TimetableRunStatus.RUNNING:
        raise BusinessRuleError(
            "Only a RUNNING timetable run can be completed.",
            details={"timetable_run_id": run.id, "status": run.status},
        )
    if status not in {
        TimetableRunStatus.SUCCEEDED,
        TimetableRunStatus.INFEASIBLE,
        TimetableRunStatus.FAILED,
    }:
        raise BusinessRuleError("Invalid completion status.")
    if objective_score is not None and not objective_score.is_finite():
        raise BusinessRuleError("objective_score must be finite.")
    if soft_penalty is not None and not soft_penalty.is_finite():
        raise BusinessRuleError("soft_penalty must be finite.")
    if soft_penalty is not None and soft_penalty < 0:
        raise BusinessRuleError("soft_penalty cannot be negative.")
    if execution_time_ms is not None and execution_time_ms < 0:
        raise BusinessRuleError("execution_time_ms cannot be negative.")
    validation = validate_timetable_run(db, run.id) if validate else None
    if (
        status == TimetableRunStatus.SUCCEEDED
        and validation is not None
        and not validation.is_valid
    ):
        raise BusinessRuleError(
            "A run with hard conflicts cannot be marked SUCCEEDED.",
            details={
                "timetable_run_id": run.id,
                "hard_conflicts": validation.hard_conflict_count,
            },
        )
    run.status = status
    run.objective_score = objective_score
    run.hard_conflicts = validation.hard_conflict_count if validation is not None else 0
    run.soft_penalty = soft_penalty
    run.execution_time_ms = execution_time_ms
    return commit_and_refresh(db, run)


def cancel_timetable_run(db: Session, timetable_run_id: int) -> TimetableRun:
    run = get_timetable_run(db, timetable_run_id)
    if run.status not in {
        TimetableRunStatus.PENDING,
        TimetableRunStatus.RUNNING,
    }:
        raise BusinessRuleError(
            "Only a PENDING or RUNNING timetable run can be cancelled.",
            details={"timetable_run_id": run.id, "status": run.status},
        )
    if run.is_published:
        raise ResourceInUseError("A published run cannot be cancelled.")
    run.status = TimetableRunStatus.CANCELLED
    return commit_and_refresh(db, run)


def delete_timetable_run(
    db: Session,
    timetable_run_id: int,
) -> MessageResponse:
    run = get_timetable_run(db, timetable_run_id)
    if run.status != TimetableRunStatus.PENDING or run.is_published:
        raise ResourceInUseError("Only an unpublished PENDING run can be deleted.")
    entry_id = db.scalar(
        select(TimetableEntry.id).where(TimetableEntry.timetable_run_id == run.id).limit(1)
    )
    if entry_id is not None:
        raise ResourceInUseError(
            "Delete the run's entries before deleting the run.",
            details={"timetable_entry_id": entry_id},
        )
    commit_delete(db, run)
    return MessageResponse(message="Timetable run deleted successfully.")
