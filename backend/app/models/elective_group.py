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
    String,
    UniqueConstraint,
    text,
    true,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

if TYPE_CHECKING:
    from app.models.curriculum_course import CurriculumCourse
    from app.models.program_semester import ProgramSemester


class ElectiveGroup(Base):
    __tablename__ = "elective_groups"
    __table_args__ = (
        UniqueConstraint(
            "program_semester_id",
            "name",
            name="uq_elective_groups_semester_name",
        ),
        CheckConstraint(
            "required_choices > 0",
            name="required_choices_positive",
        ),
    )

    id: Mapped[int] = mapped_column(Integer, Identity(), primary_key=True)
    program_semester_id: Mapped[int] = mapped_column(
        ForeignKey("program_semesters.id"),
        nullable=False,
    )
    name: Mapped[str] = mapped_column(String(150), nullable=False)
    required_choices: Mapped[int] = mapped_column(
        SmallInteger,
        nullable=False,
        default=1,
        server_default=text("1"),
    )
    is_active: Mapped[bool] = mapped_column(
        Boolean,
        nullable=False,
        default=True,
        server_default=true(),
    )

    program_semester: Mapped[ProgramSemester] = relationship(
        "ProgramSemester",
        back_populates="elective_groups",
    )
    curriculum_courses: Mapped[list[CurriculumCourse]] = relationship(
        "CurriculumCourse",
        back_populates="elective_group",
        lazy="selectin",
    )
