from datetime import date

from sqlalchemy import func, select, update
from sqlalchemy.orm import Session

from app.core.exceptions import BusinessRuleError, ResourceInUseError
from app.models.academic_term import AcademicTerm
from app.models.academic_year import AcademicYear
from app.schemas.academic_year import (
    AcademicYearCreate,
    AcademicYearRead,
    AcademicYearUpdate,
)
from app.schemas.common import MessageResponse, PaginatedResponse, PaginationParams
from app.services.academic._common import (
    apply_changes,
    commit_and_refresh,
    commit_delete,
    commit_transaction,
    ensure_unique,
    paginated_rows,
    require_by_id,
    validated_changes,
)


def _validate_date_range(start_date: date, end_date: date) -> None:
    if end_date <= start_date:
        raise BusinessRuleError("end_date must be after start_date.")


def _validate_name_matches_dates(
    name: str,
    start_date: date,
    end_date: date,
) -> None:
    first_year, second_year = (int(value) for value in name.split("/"))
    if start_date.year != first_year or end_date.year != second_year:
        raise BusinessRuleError(
            "Academic-year dates must correspond to the years in its name.",
            details={
                "name": name,
                "start_date": start_date,
                "end_date": end_date,
            },
        )


def _ensure_no_date_overlap(
    db: Session,
    start_date: date,
    end_date: date,
    *,
    exclude_id: int | None = None,
) -> None:
    statement = select(AcademicYear.id).where(
        AcademicYear.start_date <= end_date,
        AcademicYear.end_date >= start_date,
    )
    if exclude_id is not None:
        statement = statement.where(AcademicYear.id != exclude_id)

    overlapping_year_id = db.scalar(statement.limit(1))
    if overlapping_year_id is not None:
        raise BusinessRuleError(
            "Academic-year date ranges cannot overlap.",
            details={
                "overlapping_academic_year_id": overlapping_year_id,
                "requested_start_date": start_date,
                "requested_end_date": end_date,
            },
        )


def get_academic_year(db: Session, academic_year_id: int) -> AcademicYear:
    return require_by_id(db, AcademicYear, academic_year_id, "Academic year")


def list_academic_years(
    db: Session,
    pagination: PaginationParams,
) -> PaginatedResponse[AcademicYearRead]:
    statement = select(AcademicYear).order_by(
        AcademicYear.start_date.desc(),
        AcademicYear.id.desc(),
    )
    count_statement = select(func.count()).select_from(AcademicYear)
    rows, total = paginated_rows(db, statement, count_statement, pagination)
    return PaginatedResponse[AcademicYearRead](
        items=[AcademicYearRead.model_validate(row) for row in rows],
        total=total,
        page=pagination.page,
        page_size=pagination.page_size,
    )


def create_academic_year(
    db: Session,
    payload: AcademicYearCreate,
) -> AcademicYear:
    _validate_date_range(payload.start_date, payload.end_date)
    _validate_name_matches_dates(
        payload.name,
        payload.start_date,
        payload.end_date,
    )
    _ensure_no_date_overlap(db, payload.start_date, payload.end_date)
    ensure_unique(
        db,
        AcademicYear,
        "Academic year",
        ["name"],
        AcademicYear.name == payload.name,
    )
    academic_year = AcademicYear(**payload.model_dump(), is_current=False)
    db.add(academic_year)
    return commit_and_refresh(db, academic_year)


def update_academic_year(
    db: Session,
    academic_year_id: int,
    payload: AcademicYearUpdate,
) -> AcademicYear:
    academic_year = get_academic_year(db, academic_year_id)
    changes = validated_changes(
        payload,
        non_nullable_fields=("name", "start_date", "end_date"),
    )
    name = changes.get("name", academic_year.name)
    start_date = changes.get("start_date", academic_year.start_date)
    end_date = changes.get("end_date", academic_year.end_date)
    _validate_date_range(start_date, end_date)
    _validate_name_matches_dates(name, start_date, end_date)
    _ensure_no_date_overlap(
        db,
        start_date,
        end_date,
        exclude_id=academic_year.id,
    )

    ensure_unique(
        db,
        AcademicYear,
        "Academic year",
        ["name"],
        AcademicYear.name == name,
        exclude_id=academic_year.id,
    )

    outside_term = db.scalar(
        select(AcademicTerm.id)
        .where(
            AcademicTerm.academic_year_id == academic_year.id,
            (
                (AcademicTerm.start_date < start_date)
                | (AcademicTerm.end_date > end_date)
            ),
        )
        .limit(1)
    )
    if outside_term is not None:
        raise BusinessRuleError(
            "The new academic-year dates would exclude an existing term.",
            details={
                "academic_year_id": academic_year.id,
                "academic_term_id": outside_term,
            },
        )

    apply_changes(academic_year, changes)
    return commit_and_refresh(db, academic_year)


def set_current_academic_year(
    db: Session,
    academic_year_id: int,
) -> AcademicYear:
    academic_year = get_academic_year(db, academic_year_id)

    db.execute(select(AcademicYear.id).with_for_update()).all()
    db.execute(update(AcademicYear).values(is_current=False))
    academic_year.is_current = True
    commit_transaction(db)

    db.refresh(academic_year)
    return academic_year


def delete_academic_year(
    db: Session,
    academic_year_id: int,
) -> MessageResponse:
    academic_year = get_academic_year(db, academic_year_id)
    if academic_year.is_current:
        raise ResourceInUseError(
            "The current academic year cannot be deleted.",
            details={"academic_year_id": academic_year.id},
        )

    academic_term_id = db.scalar(
        select(AcademicTerm.id)
        .where(AcademicTerm.academic_year_id == academic_year.id)
        .limit(1)
    )
    if academic_term_id is not None:
        raise ResourceInUseError(
            "Academic years with terms cannot be deleted.",
            details={
                "academic_year_id": academic_year.id,
                "academic_term_id": academic_term_id,
            },
        )

    commit_delete(db, academic_year)
    return MessageResponse(message="Academic year deleted successfully.")
