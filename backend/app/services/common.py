from collections.abc import Sequence
from typing import Any

from app.core.exceptions import (
    BusinessRuleError,
    DuplicateResourceError,
    InactiveResourceError,
    ResourceNotFoundError,
)
from app.database import Base
from app.schemas.common import PaginationParams
from pydantic import BaseModel
from sqlalchemy import Select, func, inspect, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

UNIQUE_CONSTRAINT_DETAILS: dict[str, tuple[str, list[str]]] = {
    "uq_faculties_code": ("Faculty", ["code"]),
    "uq_levels_code": ("Level", ["code"]),
    "uq_study_programs_faculty_level_code": (
        "Study program",
        ["faculty_id", "level_id", "code"],
    ),
    "uq_academic_years_name": ("Academic year", ["name"]),
    "uq_current_academic_year": ("Academic year", ["is_current"]),
    "uq_academic_terms_year_type": (
        "Academic term",
        ["academic_year_id", "term_type"],
    ),
    "uq_program_semesters_program_number": (
        "Program semester",
        ["study_program_id", "semester_number"],
    ),
    "uq_courses_code": ("Course", ["code"]),
    "uq_elective_groups_semester_name": (
        "Elective group",
        ["program_semester_id", "name"],
    ),
    "uq_curriculum_courses_semester_course": (
        "Curriculum course",
        ["program_semester_id", "course_id"],
    ),
}


def normalize_code(value: str) -> str:
    """Return the canonical form used by code-bearing academic entities."""

    return value.strip().upper()


def _raise_translated_integrity_error(error: IntegrityError) -> None:
    original_error = getattr(error, "orig", None)
    diagnostic = getattr(original_error, "diag", None)
    constraint_name = getattr(diagnostic, "constraint_name", None)

    if not isinstance(constraint_name, str):
        raise error

    duplicate_details = UNIQUE_CONSTRAINT_DETAILS.get(constraint_name)

    if duplicate_details is not None:
        resource_name, fields = duplicate_details
        raise DuplicateResourceError(
            resource_name,
            fields=fields,
        ) from error

    raise error


def require_by_id[ModelT: Base](
    db: Session,
    model_type: type[ModelT],
    identifier: int,
    resource_name: str,
) -> ModelT:
    instance = db.get(model_type, identifier)

    if instance is None:
        raise ResourceNotFoundError(resource_name, identifier)

    return instance


def require_active(instance: Any, resource_name: str) -> None:
    if hasattr(instance, "is_active") and not instance.is_active:
        raise InactiveResourceError(
            f"{resource_name} must be active for this operation.",
            details={
                "resource": resource_name,
                "identifier": str(instance.id),
            },
        )


def ensure_unique[ModelT: Base](
    db: Session,
    model_type: type[ModelT],
    resource_name: str,
    fields: Sequence[str],
    *conditions: Any,
    exclude_id: int | None = None,
) -> None:
    mapper = inspect(model_type)
    identifier_column = mapper.primary_key[0]
    statement = select(identifier_column).where(*conditions)

    if exclude_id is not None:
        statement = statement.where(identifier_column != exclude_id)

    if db.scalar(statement.limit(1)) is not None:
        raise DuplicateResourceError(
            resource_name,
            fields=list(fields),
        )


def validated_changes(
    payload: BaseModel,
    *,
    non_nullable_fields: Sequence[str] = (),
) -> dict[str, Any]:
    changes = payload.model_dump(exclude_unset=True)
    if not changes:
        raise BusinessRuleError("At least one field must be provided.")

    null_fields = sorted(
        field_name
        for field_name in non_nullable_fields
        if field_name in changes and changes[field_name] is None
    )
    if null_fields:
        raise BusinessRuleError(
            "Required fields cannot be null.",
            details={"fields": null_fields},
        )
    return changes


def apply_changes(instance: Any, changes: dict[str, Any]) -> None:
    for field_name, value in changes.items():
        setattr(instance, field_name, value)


def commit_transaction(db: Session) -> None:
    try:
        db.commit()
    except IntegrityError as error:
        db.rollback()
        _raise_translated_integrity_error(error)
    except Exception:
        db.rollback()
        raise


def flush_transaction(db: Session) -> None:
    try:
        db.flush()
    except IntegrityError as error:
        db.rollback()
        _raise_translated_integrity_error(error)
    except Exception:
        db.rollback()
        raise


def commit_and_refresh[ModelT: Base](
    db: Session,
    instance: ModelT,
) -> ModelT:
    commit_transaction(db)
    db.refresh(instance)

    return instance


def commit_delete[ModelT: Base](
    db: Session,
    instance: ModelT,
) -> None:
    db.delete(instance)
    commit_transaction(db)


def paginated_rows(
    db: Session,
    statement: Select[Any],
    count_statement: Select[Any],
    pagination: PaginationParams,
) -> tuple[list[Any], int]:
    total = int(db.scalar(count_statement) or 0)
    rows = list(db.scalars(statement.offset(pagination.offset).limit(pagination.page_size)).all())
    return rows, total


def model_count_statement[ModelT: Base](
    model_type: type[ModelT],
) -> Select[Any]:
    return select(func.count()).select_from(model_type)
