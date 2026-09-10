from collections.abc import Sequence

from app.core.exceptions import (
    BusinessRuleError,
    DuplicateResourceError,
    ResourceInUseError,
)
from app.models.course_session import CourseSession
from app.models.enums import (
    AssignmentSource,
    TimetableRunStatus,
    TimetableSourceType,
)
from app.models.room import Room
from app.models.timetable_entry import TimetableEntry
from app.models.timetable_run import TimetableRun
from app.schemas.common import MessageResponse, PaginatedResponse, PaginationParams
from app.schemas.timetable_entry import (
    TimetableEntryCreate,
    TimetableEntryRead,
    TimetableEntryUpdate,
)
from app.services.common import (
    apply_changes,
    commit_and_refresh,
    commit_delete,
    commit_transaction,
    flush_transaction,
    paginated_rows,
    require_by_id,
    validated_changes,
)
from app.services.timetable.types import TimetableAssignment
from app.services.timetable.validation import collect_entry_conflicts
from sqlalchemy import func, select
from sqlalchemy.orm import Session


def _lock_run(db: Session, timetable_run_id: int) -> TimetableRun:
    run = db.scalar(
        select(TimetableRun).where(TimetableRun.id == timetable_run_id).with_for_update()
    )
    if run is None:
        return require_by_id(
            db,
            TimetableRun,
            timetable_run_id,
            "Timetable run",
        )
    return run


def _manual_assignment_source(run: TimetableRun) -> AssignmentSource:
    if run.source_type == TimetableSourceType.MANUAL:
        return AssignmentSource.MANUAL
    if run.source_type == TimetableSourceType.IMPORTED:
        return AssignmentSource.IMPORTED
    raise BusinessRuleError(
        "Generated and reoptimized entries must be persisted by the generation "
        "or reoptimization workflow.",
        details={"timetable_run_id": run.id, "source_type": run.source_type},
    )


def _require_manual_entry_mutability(run: TimetableRun) -> AssignmentSource:
    if run.is_published:
        raise ResourceInUseError("Published timetable entries are immutable.")
    if run.status != TimetableRunStatus.PENDING:
        raise ResourceInUseError(
            "Manual or imported entries can only change while the run is PENDING.",
            details={"timetable_run_id": run.id, "status": run.status},
        )
    return _manual_assignment_source(run)


def _ensure_unique_occurrence(
    db: Session,
    *,
    timetable_run_id: int,
    course_session_id: int,
    occurrence_number: int,
    exclude_id: int | None = None,
) -> None:
    statement = select(TimetableEntry.id).where(
        TimetableEntry.timetable_run_id == timetable_run_id,
        TimetableEntry.course_session_id == course_session_id,
        TimetableEntry.occurrence_number == occurrence_number,
    )
    if exclude_id is not None:
        statement = statement.where(TimetableEntry.id != exclude_id)
    if db.scalar(statement.limit(1)) is not None:
        raise DuplicateResourceError(
            "Timetable entry",
            fields=[
                "timetable_run_id",
                "course_session_id",
                "occurrence_number",
            ],
        )


def _validate_assignment(
    db: Session,
    *,
    timetable_run_id: int,
    course_session_id: int,
    occurrence_number: int,
    room_id: int,
    start_slot_id: int,
    exclude_entry_id: int | None = None,
) -> None:
    _ensure_unique_occurrence(
        db,
        timetable_run_id=timetable_run_id,
        course_session_id=course_session_id,
        occurrence_number=occurrence_number,
        exclude_id=exclude_entry_id,
    )
    conflicts = collect_entry_conflicts(
        db,
        timetable_run_id=timetable_run_id,
        course_session_id=course_session_id,
        occurrence_number=occurrence_number,
        room_id=room_id,
        start_slot_id=start_slot_id,
        exclude_entry_id=exclude_entry_id,
    )
    if conflicts:
        first = conflicts[0]
        raise BusinessRuleError(
            first.message,
            details={
                "conflict_code": first.code,
                **first.details,
            },
        )


def get_timetable_entry(
    db: Session,
    timetable_entry_id: int,
) -> TimetableEntry:
    return require_by_id(
        db,
        TimetableEntry,
        timetable_entry_id,
        "Timetable entry",
    )


def list_timetable_entries(
    db: Session,
    pagination: PaginationParams,
    *,
    timetable_run_id: int | None = None,
    course_session_id: int | None = None,
    room_id: int | None = None,
    is_locked: bool | None = None,
) -> PaginatedResponse[TimetableEntryRead]:
    filters = []
    if timetable_run_id is not None:
        require_by_id(db, TimetableRun, timetable_run_id, "Timetable run")
        filters.append(TimetableEntry.timetable_run_id == timetable_run_id)
    if course_session_id is not None:
        require_by_id(
            db,
            CourseSession,
            course_session_id,
            "Course session",
        )
        filters.append(TimetableEntry.course_session_id == course_session_id)
    if room_id is not None:
        require_by_id(db, Room, room_id, "Room")
        filters.append(TimetableEntry.room_id == room_id)
    if is_locked is not None:
        filters.append(TimetableEntry.is_locked.is_(is_locked))
    statement = (
        select(TimetableEntry)
        .where(*filters)
        .order_by(
            TimetableEntry.timetable_run_id,
            TimetableEntry.start_slot_id,
            TimetableEntry.course_session_id,
            TimetableEntry.occurrence_number,
        )
    )
    count_statement = select(func.count()).select_from(TimetableEntry).where(*filters)
    rows, total = paginated_rows(db, statement, count_statement, pagination)
    return PaginatedResponse[TimetableEntryRead](
        items=[TimetableEntryRead.model_validate(row) for row in rows],
        total=total,
        page=pagination.page,
        page_size=pagination.page_size,
    )


def create_timetable_entry(
    db: Session,
    payload: TimetableEntryCreate,
) -> TimetableEntry:
    run = _lock_run(db, payload.timetable_run_id)
    assignment_source = _require_manual_entry_mutability(run)
    _validate_assignment(
        db,
        timetable_run_id=run.id,
        course_session_id=payload.course_session_id,
        occurrence_number=payload.occurrence_number,
        room_id=payload.room_id,
        start_slot_id=payload.start_slot_id,
    )
    values = payload.model_dump(exclude={"assignment_source"})
    entry = TimetableEntry(
        **values,
        assignment_source=assignment_source,
    )
    db.add(entry)
    return commit_and_refresh(db, entry)


def update_timetable_entry(
    db: Session,
    timetable_entry_id: int,
    payload: TimetableEntryUpdate,
) -> TimetableEntry:
    entry = get_timetable_entry(db, timetable_entry_id)
    run = _lock_run(db, entry.timetable_run_id)
    assignment_source = _require_manual_entry_mutability(run)
    changes = validated_changes(payload)
    immutable = {
        "timetable_run_id",
        "course_session_id",
        "occurrence_number",
        "assignment_source",
    }.intersection(changes)
    if immutable:
        raise BusinessRuleError(
            "Entry identity and assignment_source are immutable; delete and "
            "recreate the entry instead.",
            details={"immutable_fields": sorted(immutable)},
        )
    room_id = changes.get("room_id", entry.room_id)
    start_slot_id = changes.get("start_slot_id", entry.start_slot_id)
    _validate_assignment(
        db,
        timetable_run_id=entry.timetable_run_id,
        course_session_id=entry.course_session_id,
        occurrence_number=entry.occurrence_number,
        room_id=room_id,
        start_slot_id=start_slot_id,
        exclude_entry_id=entry.id,
    )
    changes["assignment_source"] = assignment_source
    apply_changes(entry, changes)
    return commit_and_refresh(db, entry)


def set_timetable_entry_lock(
    db: Session,
    timetable_entry_id: int,
    *,
    is_locked: bool,
) -> TimetableEntry:
    entry = get_timetable_entry(db, timetable_entry_id)
    run = _lock_run(db, entry.timetable_run_id)
    if run.status not in {
        TimetableRunStatus.PENDING,
        TimetableRunStatus.SUCCEEDED,
    }:
        raise ResourceInUseError(
            "Entries can only be locked in PENDING or SUCCEEDED runs.",
            details={"timetable_run_id": run.id, "status": run.status},
        )
    entry.is_locked = is_locked
    return commit_and_refresh(db, entry)


def delete_timetable_entry(
    db: Session,
    timetable_entry_id: int,
) -> MessageResponse:
    entry = get_timetable_entry(db, timetable_entry_id)
    run = _lock_run(db, entry.timetable_run_id)
    _require_manual_entry_mutability(run)
    if entry.is_locked:
        raise ResourceInUseError("Unlock the timetable entry before deleting it.")
    commit_delete(db, entry)
    return MessageResponse(message="Timetable entry deleted successfully.")


def persist_solver_assignments(
    db: Session,
    timetable_run_id: int,
    assignments: Sequence[TimetableAssignment],
    *,
    preserve_locked: bool = False,
    validate_assignments: bool = True,
) -> tuple[TimetableEntry, ...]:
    """Persist solver output.

    Generation validates the complete solver result in memory immediately
    before calling this function. In that path, repeating the per-entry
    database conflict scan would turn persistence into O(n²) work. The
    default remains fully validating for other callers.
    """
    run = _lock_run(db, timetable_run_id)
    if run.status != TimetableRunStatus.RUNNING:
        raise ResourceInUseError(
            "Solver assignments can only be persisted for a RUNNING run.",
            details={"timetable_run_id": run.id, "status": run.status},
        )
    if run.source_type not in {
        TimetableSourceType.GENERATED,
        TimetableSourceType.REOPTIMIZED,
    }:
        raise BusinessRuleError("Only generated or reoptimized runs accept solver assignments.")
    existing = tuple(
        db.scalars(select(TimetableEntry).where(TimetableEntry.timetable_run_id == run.id)).all()
    )
    for entry in existing:
        if preserve_locked and entry.is_locked:
            continue
        db.delete(entry)
    flush_transaction(db)

    created: list[TimetableEntry] = []
    for assignment in assignments:
        if assignment.assignment_source != AssignmentSource.SOLVER:
            raise BusinessRuleError("New solver assignments must use assignment_source=SOLVER.")
        if assignment.is_locked:
            raise BusinessRuleError(
                "New solver assignments cannot be locked automatically; lock "
                "them explicitly after a successful run."
            )
        if validate_assignments:
            _validate_assignment(
                db,
                timetable_run_id=run.id,
                course_session_id=assignment.course_session_id,
                occurrence_number=assignment.occurrence_number,
                room_id=assignment.room_id,
                start_slot_id=assignment.start_slot_id,
            )
        entry = TimetableEntry(
            timetable_run_id=run.id,
            course_session_id=assignment.course_session_id,
            occurrence_number=assignment.occurrence_number,
            room_id=assignment.room_id,
            start_slot_id=assignment.start_slot_id,
            is_locked=False,
            assignment_source=AssignmentSource.SOLVER,
        )
        db.add(entry)
        if validate_assignments:
            flush_transaction(db)
        created.append(entry)
    if not validate_assignments:
        flush_transaction(db)
    commit_transaction(db)
    for entry in created:
        db.refresh(entry)
    return tuple(created)
