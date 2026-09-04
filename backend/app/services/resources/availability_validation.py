from datetime import time
from typing import Any, cast

from app.core.exceptions import BusinessRuleError
from app.models.enums import AvailabilityType
from sqlalchemy import select
from sqlalchemy.orm import InstrumentedAttribute, Session


def mapped_attribute(
    model_type: type[Any],
    attribute_name: str,
) -> InstrumentedAttribute[Any]:
    return cast(
        InstrumentedAttribute[Any],
        getattr(model_type, attribute_name),
    )


def validate_availability_values(
    *,
    day_of_week: int,
    start_time: time,
    end_time: time,
    availability_type: AvailabilityType,
    preference_weight: int | None,
) -> None:
    if not 1 <= int(day_of_week) <= 7:
        raise BusinessRuleError("day_of_week must be between 1 and 7.")

    if end_time <= start_time:
        raise BusinessRuleError("end_time must be after start_time.")

    weighted_types = {
        AvailabilityType.PREFERRED,
        AvailabilityType.AVOID,
    }

    if availability_type in weighted_types and preference_weight is None:
        raise BusinessRuleError("PREFERRED and AVOID windows require preference_weight.")

    if availability_type not in weighted_types and preference_weight is not None:
        raise BusinessRuleError(
            "AVAILABLE and UNAVAILABLE windows must not have preference_weight."
        )

    if preference_weight is not None and preference_weight < 0:
        raise BusinessRuleError("preference_weight cannot be negative.")


def ensure_no_overlapping_window(
    db: Session,
    model_type: type[Any],
    *,
    owner_field: str,
    owner_id: int,
    academic_term_id: int,
    day_of_week: int,
    start_time: time,
    end_time: time,
    resource_name: str,
    exclude_id: int | None = None,
) -> None:
    identifier_column = mapped_attribute(model_type, "id")
    owner_column = mapped_attribute(model_type, owner_field)
    academic_term_column = mapped_attribute(
        model_type,
        "academic_term_id",
    )
    day_column = mapped_attribute(model_type, "day_of_week")
    start_column = mapped_attribute(model_type, "start_time")
    end_column = mapped_attribute(model_type, "end_time")

    statement = select(identifier_column).where(
        owner_column == owner_id,
        academic_term_column == academic_term_id,
        day_column == day_of_week,
        start_column < end_time,
        end_column > start_time,
    )

    if exclude_id is not None:
        statement = statement.where(identifier_column != exclude_id)

    overlapping_id = db.scalar(statement.limit(1))

    if overlapping_id is not None:
        raise BusinessRuleError(
            f"{resource_name} windows cannot overlap for the same term and day.",
            details={
                owner_field: owner_id,
                "academic_term_id": academic_term_id,
                "day_of_week": int(day_of_week),
                "overlapping_window_id": overlapping_id,
            },
        )
