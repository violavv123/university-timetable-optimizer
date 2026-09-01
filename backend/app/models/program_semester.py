from __future__ import annotations

from typing import TYPE_CHECKING

from app.database import Base
from sqlalchemy import (
    Boolean,
    CheckConstraint,
    ForeignKey,
    Identity,
    Integer,
    SmallInteger,
    UniqueConstraint,
    true,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

if TYPE_CHECKING:
    from app.models.curriculum_course import CurriculumCourse
    from app.models.elective_group import ElectiveGroup
    from app.models.student_group import StudentGroup
    from app.models.study_program import StudyProgram


class ProgramSemester(Base):
    __tablename__ = "program_semesters"
    __table_args__ = (
        UniqueConstraint(
            "study_program_id",
            "semester_number",
            name="uq_program_semesters_program_number",
        ),
        CheckConstraint(
            "semester_number > 0",
            name="semester_number_positive",
        ),
    )

    id: Mapped[int] = mapped_column(Integer, Identity(), primary_key=True)
    study_program_id: Mapped[int] = mapped_column(
        ForeignKey("study_programs.id"),
        nullable=False,
    )
    semester_number: Mapped[int] = mapped_column(
        SmallInteger,
        nullable=False,
    )
    is_active: Mapped[bool] = mapped_column(
        Boolean,
        nullable=False,
        default=True,
        server_default=true(),
    )

    study_program: Mapped[StudyProgram] = relationship(
        "StudyProgram",
        back_populates="program_semesters",
    )
    elective_groups: Mapped[list[ElectiveGroup]] = relationship(
        "ElectiveGroup",
        back_populates="program_semester",
        lazy="selectin",
    )
    curriculum_courses: Mapped[list[CurriculumCourse]] = relationship(
        "CurriculumCourse",
        back_populates="program_semester",
        lazy="selectin",
    )

    student_groups: Mapped[list[StudentGroup]] = relationship(
        "StudentGroup",
        back_populates="program_semester",
        lazy="selectin",
    )
