from datetime import time
from typing import Any

from app.models.enums import DayOfWeek, TimetableRunStatus, TimetableSourceType
from app.routers.crud import register_crud_routes
from app.routers.dependencies import DbSession, TimetableSolverDependency
from app.schemas.scheduler import SchedulingConflictRead, TimetableGenerationRequest
from app.schemas.scheduler import TimetableValidationResult as TimetableValidationResponse
from app.schemas.timetable_entry import (
    TimetableEntryCreate,
    TimetableEntryLockUpdate,
    TimetableEntryRead,
    TimetableEntryUpdate,
)
from app.schemas.timetable_run import TimetableRunCreate, TimetableRunRead, TimetableRunUpdate
from app.services.timetable import timetable_entry, timetable_run
from app.services.timetable.export import (
    export_published_timetable_csv,
)
from app.services.timetable.generation import generate_timetable
from app.services.timetable.publication import publish_timetable_run, unpublish_timetable_run
from app.services.timetable.reoptimization import prepare_reoptimized_run
from app.services.timetable.types import TimetableConflict
from app.services.timetable.validation import validate_timetable_run
from fastapi import APIRouter, Path, Response
from pydantic import BaseModel, ConfigDict, Field

router = APIRouter(prefix="/timetables", tags=["Timetables"])


class TimetableRunFilters(BaseModel):
    model_config = ConfigDict(extra="forbid")

    academic_term_id: int | None = Field(default=None, gt=0)
    scheduling_profile_id: int | None = Field(default=None, gt=0)
    status: TimetableRunStatus | None = None
    is_published: bool | None = None


class TimetableEntryFilters(BaseModel):
    model_config = ConfigDict(extra="forbid")

    timetable_run_id: int | None = Field(default=None, gt=0)
    course_session_id: int | None = Field(default=None, gt=0)
    room_id: int | None = Field(default=None, gt=0)
    is_locked: bool | None = None


register_crud_routes(
    router,
    path="/runs",
    resource_name="timetable run",
    read_schema=TimetableRunRead,
    create_schema=TimetableRunCreate,
    update_schema=TimetableRunUpdate,
    get_service=timetable_run.get_timetable_run,
    list_service=timetable_run.list_timetable_runs,
    create_service=timetable_run.create_timetable_run,
    update_service=timetable_run.update_timetable_run,
    delete_service=timetable_run.delete_timetable_run,
    filters_schema=TimetableRunFilters,
)
register_crud_routes(
    router,
    path="/entries",
    resource_name="timetable entry",
    read_schema=TimetableEntryRead,
    create_schema=TimetableEntryCreate,
    update_schema=TimetableEntryUpdate,
    get_service=timetable_entry.get_timetable_entry,
    list_service=timetable_entry.list_timetable_entries,
    create_service=timetable_entry.create_timetable_entry,
    update_service=timetable_entry.update_timetable_entry,
    delete_service=timetable_entry.delete_timetable_entry,
    filters_schema=TimetableEntryFilters,
)


@router.post(
    "/generate",
    response_model=TimetableRunRead,
    status_code=201,
    summary="Create and solve a generated timetable run",
)
def create_and_generate_run(
    payload: TimetableGenerationRequest,
    db: DbSession,
    solver: TimetableSolverDependency,
) -> Any:
    run = timetable_run.create_timetable_run(
        db,
        TimetableRunCreate(
            academic_term_id=payload.academic_term_id,
            scheduling_profile_id=payload.scheduling_profile_id,
            name=payload.name,
            source_type=TimetableSourceType.GENERATED,
            algorithm=payload.algorithm,
            parameters=payload.parameters.model_dump(),
        ),
    )
    return generate_timetable(db, run.id, solver)


def _positive_ids(details: dict[str, Any], singular: str, plural: str) -> list[int]:
    value = details.get(plural)
    if value is None:
        value = details.get(singular)
    if isinstance(value, int) and not isinstance(value, bool) and value > 0:
        return [value]
    if isinstance(value, (list, tuple, set)):
        return sorted(
            {
                item
                for item in value
                if isinstance(item, int) and not isinstance(item, bool) and item > 0
            }
        )
    return []


def _day_of_week(details: dict[str, Any]) -> DayOfWeek | None:
    value = details.get("day_of_week")
    try:
        return DayOfWeek(value) if value is not None else None
    except ValueError:
        return None


def _time_value(details: dict[str, Any], key: str) -> time | None:
    value = details.get(key)
    return value if isinstance(value, time) else None


def _conflict_response(conflict: TimetableConflict) -> SchedulingConflictRead:
    details = conflict.details
    return SchedulingConflictRead(
        conflict_type=conflict.code,
        message=conflict.message,
        course_session_ids=_positive_ids(
            details,
            "course_session_id",
            "course_session_ids",
        ),
        staff_member_ids=_positive_ids(details, "staff_member_id", "staff_member_ids"),
        student_group_ids=_positive_ids(details, "student_group_id", "student_group_ids"),
        room_ids=_positive_ids(details, "room_id", "room_ids"),
        day_of_week=_day_of_week(details),
        start_time=_time_value(details, "start_time"),
        end_time=_time_value(details, "end_time"),
    )


@router.post(
    "/runs/{timetable_run_id}/generate",
    response_model=TimetableRunRead,
    summary="Run the configured timetable solver",
)
def generate_run(
    db: DbSession,
    solver: TimetableSolverDependency,
    timetable_run_id: int = Path(..., gt=0),
) -> Any:
    return generate_timetable(db, timetable_run_id, solver)


@router.post(
    "/runs/{timetable_run_id}/cancel",
    response_model=TimetableRunRead,
    summary="Cancel a timetable run",
)
def cancel_run(
    db: DbSession,
    timetable_run_id: int = Path(..., gt=0),
) -> Any:
    return timetable_run.cancel_timetable_run(db, timetable_run_id)


@router.post(
    "/runs/{timetable_run_id}/publish",
    response_model=TimetableRunRead,
    summary="Publish a conflict-free timetable run",
)
def publish_run(
    db: DbSession,
    timetable_run_id: int = Path(..., gt=0),
) -> Any:
    return publish_timetable_run(db, timetable_run_id)


@router.post(
    "/runs/{timetable_run_id}/unpublish",
    response_model=TimetableRunRead,
    summary="Unpublish a timetable run",
)
def unpublish_run(
    db: DbSession,
    timetable_run_id: int = Path(..., gt=0),
) -> Any:
    return unpublish_timetable_run(db, timetable_run_id)


@router.get(
    "/runs/{timetable_run_id}/validation",
    response_model=TimetableValidationResponse,
    summary="Validate every assignment in a timetable run",
)
def validate_run(
    db: DbSession,
    timetable_run_id: int = Path(..., gt=0),
) -> TimetableValidationResponse:
    result = validate_timetable_run(db, timetable_run_id)
    return TimetableValidationResponse(
        is_valid=result.is_valid,
        hard_conflicts=result.hard_conflict_count,
        warnings=[],
        conflicts=[_conflict_response(item) for item in result.hard_conflicts],
    )


@router.get(
    "/runs/{timetable_run_id}/download",
    response_class=Response,
    summary="Download a published timetable as CSV",
)
def download_timetable(
    db: DbSession,
    timetable_run_id: int = Path(..., gt=0),
) -> Response:
    filename, csv_content = export_published_timetable_csv(
        db,
        timetable_run_id,
    )

    return Response(
        content=csv_content.encode("utf-8-sig"),
        media_type="text/csv; charset=utf-8",
        headers={"Content-Disposition": (f'attachment; filename="{filename}"')},
    )


@router.post(
    "/runs/{source_run_id}/reoptimized-run",
    response_model=TimetableRunRead,
    status_code=201,
    summary="Prepare a run that preserves locked source entries",
)
def prepare_reoptimization(
    payload: TimetableRunCreate,
    db: DbSession,
    source_run_id: int = Path(..., gt=0),
) -> Any:
    return prepare_reoptimized_run(db, source_run_id, payload)


@router.patch(
    "/entries/{timetable_entry_id}/lock",
    response_model=TimetableEntryRead,
    summary="Lock or unlock a timetable entry",
)
def set_entry_lock(
    payload: TimetableEntryLockUpdate,
    db: DbSession,
    timetable_entry_id: int = Path(..., gt=0),
) -> Any:
    return timetable_entry.set_timetable_entry_lock(
        db,
        timetable_entry_id,
        is_locked=payload.is_locked,
    )


__all__ = ["router"]
