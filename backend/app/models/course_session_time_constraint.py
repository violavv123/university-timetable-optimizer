from __future__ import annotations

from datetime import time
from typing import TYPE_CHECKING

from sqlalchemy import (
    CheckConstraint,
    Enum as SqlEnum,
    ForeignKey,
    Identity,
    Integer,
    SmallInteger,
    Time,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base
from app.models.enums import TimeConstraintType

if TYPE_CHECKING:
    from app.models.course_session import CourseSession


class CourseSessionTimeConstraint(Base):
    __tablename__ = "course_session_time_constraints"
    __table_args__ = (
        CheckConstraint(
            "day_of_week IS NULL OR day_of_week BETWEEN 1 AND 7",
            name="day_of_week_valid",
        ),
        CheckConstraint("end_time > start_time", name="valid_time_range"),
        CheckConstraint(
            "preference_weight IS NULL OR preference_weight >= 0",
            name="preference_weight_nonnegative",
        ),
    )

    id: Mapped[int] = mapped_column(Integer, Identity(), primary_key=True)
    course_session_id: Mapped[int] = mapped_column(
        ForeignKey("course_sessions.id"),
        nullable=False,
    )
    day_of_week: Mapped[int | None] = mapped_column(
        SmallInteger,
        nullable=True,
    )
    start_time: Mapped[time] = mapped_column(Time, nullable=False)
    end_time: Mapped[time] = mapped_column(Time, nullable=False)
    constraint_type: Mapped[TimeConstraintType] = mapped_column(
        SqlEnum(
            TimeConstraintType,
            name="time_constraint_type",
            validate_strings=True,
        ),
        nullable=False,
    )
    preference_weight: Mapped[int | None] = mapped_column(
        SmallInteger,
        nullable=True,
    )

    course_session: Mapped[CourseSession] = relationship(
        "CourseSession",
        back_populates="time_constraints",
    )
