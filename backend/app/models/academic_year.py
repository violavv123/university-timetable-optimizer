from __future__ import annotations

from datetime import date
from typing import TYPE_CHECKING

from app.database import Base
from sqlalchemy import (
    Boolean,
    CheckConstraint,
    Date,
    Identity,
    Index,
    Integer,
    String,
    UniqueConstraint,
    false,
    text,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

if TYPE_CHECKING:
    from app.models.academic_term import AcademicTerm


class AcademicYear(Base):
    __tablename__ = "academic_years"
    __table_args__ = (
        UniqueConstraint("name", name="uq_academic_years_name"),
        CheckConstraint(
            "end_date > start_date",
            name="valid_date_range",
        ),
        Index(
            "uq_current_academic_year",
            "is_current",
            unique=True,
            postgresql_where=text("is_current = true"),
        ),
    )

    id: Mapped[int] = mapped_column(Integer, Identity(), primary_key=True)
    name: Mapped[str] = mapped_column(String(20), nullable=False)
    start_date: Mapped[date] = mapped_column(Date, nullable=False)
    end_date: Mapped[date] = mapped_column(Date, nullable=False)
    is_current: Mapped[bool] = mapped_column(
        Boolean,
        nullable=False,
        default=False,
        server_default=false(),
    )

    academic_terms: Mapped[list[AcademicTerm]] = relationship(
        "AcademicTerm",
        back_populates="academic_year",
        lazy="selectin",
    )
