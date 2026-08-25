from __future__ import annotations

from typing import TYPE_CHECKING

from sqlalchemy import (
    Boolean,
    ForeignKey,
    Identity,
    Integer,
    String,
    UniqueConstraint,
    true,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base

if TYPE_CHECKING:
    from app.models.faculty import Faculty
    from app.models.level import Level
    from app.models.program_semester import ProgramSemester
    from app.models.program_room_preference import ProgramRoomPreference


class StudyProgram(Base):
    __tablename__ = "study_programs"
    __table_args__ = (
        UniqueConstraint(
            "faculty_id",
            "level_id",
            "code",
            name="uq_study_programs_faculty_level_code",
        ),
    )

    id: Mapped[int] = mapped_column(Integer, Identity(), primary_key=True)
    faculty_id: Mapped[int] = mapped_column(
        ForeignKey("faculties.id"),
        nullable=False,
    )
    level_id: Mapped[int] = mapped_column(
        ForeignKey("levels.id"),
        nullable=False,
    )
    code: Mapped[str] = mapped_column(String(30), nullable=False)
    name: Mapped[str] = mapped_column(String(150), nullable=False)
    is_active: Mapped[bool] = mapped_column(
        Boolean,
        nullable=False,
        default=True,
        server_default=true(),
    )

    faculty: Mapped[Faculty] = relationship(
        "Faculty",
        back_populates="study_programs",
    )
    level: Mapped[Level] = relationship(
        "Level",
        back_populates="study_programs",
    )
    program_semesters: Mapped[list[ProgramSemester]] = relationship(
        "ProgramSemester",
        back_populates="study_program",
        lazy="selectin",
    )

    room_preferences: Mapped[list[ProgramRoomPreference]] = relationship(
        "ProgramRoomPreference",
        back_populates="study_program",
        lazy="selectin",
    )
