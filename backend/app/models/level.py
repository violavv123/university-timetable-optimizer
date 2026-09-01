from __future__ import annotations

from typing import TYPE_CHECKING

from app.database import Base
from sqlalchemy import (
    Boolean,
    CheckConstraint,
    Integer,
    SmallInteger,
    String,
    UniqueConstraint,
    true,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

if TYPE_CHECKING:
    from app.models.study_program import StudyProgram


class Level(Base):
    __tablename__ = "levels"
    __table_args__ = (
        UniqueConstraint("code", name="uq_levels_code"),
        CheckConstraint(
            "semester_count > 0",
            name="ck_levels_semester_count_positive",
        ),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    code: Mapped[str] = mapped_column(String(20), nullable=False)
    name: Mapped[str] = mapped_column(String(100), nullable=False)
    semester_count: Mapped[int] = mapped_column(SmallInteger, nullable=False)
    is_active: Mapped[bool] = mapped_column(
        Boolean,
        nullable=False,
        default=True,
        server_default=true(),
    )

    study_programs: Mapped[list[StudyProgram]] = relationship(
        "StudyProgram",
        back_populates="level",
        lazy="selectin",
    )
