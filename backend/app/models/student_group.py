from __future__ import annotations

from typing import TYPE_CHECKING

from sqlalchemy import (
    Boolean,
    CheckConstraint,
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
from app.models.enums import StudentGroupType

if TYPE_CHECKING:
    from app.models.academic_term import AcademicTerm
    from app.models.program_semester import ProgramSemester
    from app.models.course_session_group import CourseSessionGroup


class StudentGroup(Base):
    __tablename__ = "student_groups"
    __table_args__ = (
        UniqueConstraint(
            "program_semester_id",
            "academic_term_id",
            "name",
            name="uq_student_groups_semester_term_name",
        ),
        CheckConstraint(
            "student_count > 0",
            name="student_count_positive",
        ),
        CheckConstraint(
            "parent_group_id IS NULL OR parent_group_id <> id",
            name="parent_group_not_self",
        ),
    )

    id: Mapped[int] = mapped_column(Integer, Identity(), primary_key=True)
    program_semester_id: Mapped[int] = mapped_column(
        ForeignKey("program_semesters.id"),
        nullable=False,
    )
    academic_term_id: Mapped[int] = mapped_column(
        ForeignKey("academic_terms.id"),
        nullable=False,
    )
    parent_group_id: Mapped[int | None] = mapped_column(
        ForeignKey("student_groups.id"),
        nullable=True,
    )
    name: Mapped[str] = mapped_column(String(100), nullable=False)
    group_type: Mapped[StudentGroupType] = mapped_column(
        SqlEnum(
            StudentGroupType,
            name="student_group_type",
            validate_strings=True,
        ),
        nullable=False,
    )
    student_count: Mapped[int] = mapped_column(Integer, nullable=False)
    is_active: Mapped[bool] = mapped_column(
        Boolean,
        nullable=False,
        default=True,
        server_default=true(),
    )

    program_semester: Mapped[ProgramSemester] = relationship(
        "ProgramSemester",
        back_populates="student_groups",
    )
    academic_term: Mapped[AcademicTerm] = relationship(
        "AcademicTerm",
        back_populates="student_groups",
    )
    parent_group: Mapped[StudentGroup | None] = relationship(
        "StudentGroup",
        remote_side="StudentGroup.id",
        back_populates="child_groups",
    )
    child_groups: Mapped[list[StudentGroup]] = relationship(
        "StudentGroup",
        back_populates="parent_group",
        lazy="selectin",
    )

    session_assignments: Mapped[list[CourseSessionGroup]] = relationship(
        "CourseSessionGroup",
        back_populates="student_group",
        lazy="selectin",
    )
