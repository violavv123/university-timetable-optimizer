from __future__ import annotations

from datetime import date
from typing import TYPE_CHECKING

from sqlalchemy import (
    Boolean,
    CheckConstraint,
    Date,
    Enum as SqlEnum,
    ForeignKey,
    Identity,
    Integer,
    String,
    UniqueConstraint,
    true,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base
from app.models.enums import TermType

if TYPE_CHECKING:
    from app.models.academic_year import AcademicYear
    from app.models.room_availability import RoomAvailability
    from app.models.staff_availability import StaffAvailability
    from app.models.student_group import StudentGroup
    from app.models.course_offering import CourseOffering
    from app.models.timetable_run import TimetableRun


class AcademicTerm(Base):
    __tablename__ = "academic_terms"
    __table_args__ = (
        UniqueConstraint(
            "academic_year_id",
            "term_type",
            name="uq_academic_terms_year_type",
        ),
        CheckConstraint(
            "end_date > start_date",
            name="valid_date_range",
        ),
    )

    id: Mapped[int] = mapped_column(Integer, Identity(), primary_key=True)
    academic_year_id: Mapped[int] = mapped_column(
        ForeignKey("academic_years.id"),
        nullable=False,
    )
    name: Mapped[str] = mapped_column(String(100), nullable=False)
    term_type: Mapped[TermType] = mapped_column(
        SqlEnum(
            TermType,
            name="term_type",
            validate_strings=True,
        ),
        nullable=False,
    )
    start_date: Mapped[date] = mapped_column(Date, nullable=False)
    end_date: Mapped[date] = mapped_column(Date, nullable=False)
    is_active: Mapped[bool] = mapped_column(
        Boolean,
        nullable=False,
        default=True,
        server_default=true(),
    )

    academic_year: Mapped[AcademicYear] = relationship(
        "AcademicYear",
        back_populates="academic_terms",
    )

    staff_availabilities: Mapped[list[StaffAvailability]] = relationship(
        "StaffAvailability",
        back_populates="academic_term",
        lazy="selectin",
    )

    student_groups: Mapped[list[StudentGroup]] = relationship(
        "StudentGroup",
        back_populates="academic_term",
        lazy="selectin",
    )

    room_availabilities: Mapped[list[RoomAvailability]] = relationship(
        "RoomAvailability",
        back_populates="academic_term",
        lazy="selectin",
    )

    course_offerings: Mapped[list[CourseOffering]] = relationship(
        "CourseOffering",
        back_populates="academic_term",
        lazy="selectin",
    )

    timetable_runs: Mapped[list[TimetableRun]] = relationship(
        "TimetableRun",
        back_populates="academic_term",
        lazy="selectin",
    )
