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
    text,
    true,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

if TYPE_CHECKING:
    from app.models.room import Room
    from app.models.study_program import StudyProgram


class ProgramRoomPreference(Base):
    __tablename__ = "program_room_preferences"
    __table_args__ = (
        UniqueConstraint(
            "study_program_id",
            "room_id",
            name="uq_program_room_preferences_program_room",
        ),
        CheckConstraint(
            "penalty_weight >= 0",
            name="penalty_weight_nonnegative",
        ),
    )

    id: Mapped[int] = mapped_column(Integer, Identity(), primary_key=True)
    study_program_id: Mapped[int] = mapped_column(
        ForeignKey("study_programs.id"),
        nullable=False,
    )
    room_id: Mapped[int] = mapped_column(
        ForeignKey("rooms.id"),
        nullable=False,
    )
    penalty_weight: Mapped[int] = mapped_column(
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

    study_program: Mapped[StudyProgram] = relationship(
        "StudyProgram",
        back_populates="room_preferences",
    )
    room: Mapped[Room] = relationship(
        "Room",
        back_populates="program_preferences",
    )
