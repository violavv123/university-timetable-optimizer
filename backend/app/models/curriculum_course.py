from __future__ import annotations

from decimal import Decimal
from typing import TYPE_CHECKING

from sqlalchemy import (
    Boolean,
    CheckConstraint,
    Enum as SqlEnum,
    ForeignKey,
    Identity,
    Integer,
    Numeric,
    SmallInteger,
    UniqueConstraint,
    text,
    true,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base
from app.models.enums import CourseType

if TYPE_CHECKING:
    from app.models.course import Course
    from app.models.elective_group import ElectiveGroup
    from app.models.program_semester import ProgramSemester
    from app.models.course_offering import CourseOffering


class CurriculumCourse(Base):
    __tablename__ = "curriculum_courses"
    __table_args__ = (
        UniqueConstraint(
            "program_semester_id",
            "course_id",
            name="uq_curriculum_courses_semester_course",
        ),
        CheckConstraint("ects > 0", name="ects_positive"),
        CheckConstraint(
            "lecture_periods_per_week >= 0",
            name="lecture_periods_nonnegative",
        ),
        CheckConstraint(
            "numerical_periods_per_week >= 0",
            name="numerical_periods_nonnegative",
        ),
        CheckConstraint(
            "laboratory_periods_per_week >= 0",
            name="laboratory_periods_nonnegative",
        ),
        CheckConstraint(
            "(lecture_periods_per_week + numerical_periods_per_week + "
            "laboratory_periods_per_week) > 0",
            name="weekly_periods_positive",
        ),
    )

    id: Mapped[int] = mapped_column(Integer, Identity(), primary_key=True)
    program_semester_id: Mapped[int] = mapped_column(
        ForeignKey("program_semesters.id"),
        nullable=False,
    )
    course_id: Mapped[int] = mapped_column(
        ForeignKey("courses.id"),
        nullable=False,
    )
    course_type: Mapped[CourseType] = mapped_column(
        SqlEnum(
            CourseType,
            name="course_type",
            validate_strings=True,
        ),
        nullable=False,
    )
    elective_group_id: Mapped[int | None] = mapped_column(
        ForeignKey("elective_groups.id"),
        nullable=True,
    )
    ects: Mapped[Decimal] = mapped_column(Numeric(4, 1), nullable=False)
    lecture_periods_per_week: Mapped[int] = mapped_column(
        SmallInteger,
        nullable=False,
        default=0,
        server_default=text("0"),
    )
    numerical_periods_per_week: Mapped[int] = mapped_column(
        SmallInteger,
        nullable=False,
        default=0,
        server_default=text("0"),
    )
    laboratory_periods_per_week: Mapped[int] = mapped_column(
        SmallInteger,
        nullable=False,
        default=0,
        server_default=text("0"),
    )
    is_active: Mapped[bool] = mapped_column(
        Boolean,
        nullable=False,
        default=True,
        server_default=true(),
    )

    program_semester: Mapped[ProgramSemester] = relationship(
        "ProgramSemester",
        back_populates="curriculum_courses",
    )
    course: Mapped[Course] = relationship(
        "Course",
        back_populates="curriculum_courses",
    )
    elective_group: Mapped[ElectiveGroup | None] = relationship(
        "ElectiveGroup",
        back_populates="curriculum_courses",
    )

    course_offerings: Mapped[list[CourseOffering]] = relationship(
        "CourseOffering",
        back_populates="curriculum_course",
        lazy="selectin",
    )
