from __future__ import annotations

from datetime import datetime
from typing import TYPE_CHECKING

from sqlalchemy import (
    Boolean,
    CheckConstraint,
    DateTime,
    Enum as SqlEnum,
    ForeignKey,
    Identity,
    Index,
    Integer,
    SmallInteger,
    UniqueConstraint,
    false,
    func,
    text,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base
from app.models.enums import AssignmentSource

if TYPE_CHECKING:
    from app.models.course_session import CourseSession
    from app.models.room import Room
    from app.models.time_slot import TimeSlot
    from app.models.timetable_run import TimetableRun


class TimetableEntry(Base):
    __tablename__ = "timetable_entries"
    __table_args__ = (
        UniqueConstraint(
            "timetable_run_id",
            "course_session_id",
            "occurrence_number",
            name="uq_timetable_entries_run_session_occurrence",
        ),
        Index(
            "ix_timetable_entries_run_start_slot",
            "timetable_run_id",
            "start_slot_id",
        ),
        Index(
            "ix_timetable_entries_room_id",
            "room_id",
        ),
        CheckConstraint(
            "occurrence_number > 0",
            name="occurrence_number_positive",
        ),
    )

    id: Mapped[int] = mapped_column(Integer, Identity(), primary_key=True)
    timetable_run_id: Mapped[int] = mapped_column(
        ForeignKey("timetable_runs.id"),
        nullable=False,
    )
    course_session_id: Mapped[int] = mapped_column(
        ForeignKey("course_sessions.id"),
        nullable=False,
    )
    occurrence_number: Mapped[int] = mapped_column(
        SmallInteger,
        nullable=False,
    )
    room_id: Mapped[int] = mapped_column(
        ForeignKey("rooms.id"),
        nullable=False,
    )
    start_slot_id: Mapped[int] = mapped_column(
        ForeignKey("time_slots.id"),
        nullable=False,
    )
    is_locked: Mapped[bool] = mapped_column(
        Boolean,
        nullable=False,
        default=False,
        server_default=false(),
    )
    assignment_source: Mapped[AssignmentSource] = mapped_column(
        SqlEnum(
            AssignmentSource,
            name="assignment_source",
            validate_strings=True,
        ),
        nullable=False,
        default=AssignmentSource.SOLVER,
        server_default=text("'SOLVER'"),
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        server_default=func.now(),
    )

    timetable_run: Mapped[TimetableRun] = relationship(
        "TimetableRun",
        back_populates="timetable_entries",
    )
    course_session: Mapped[CourseSession] = relationship(
        "CourseSession",
        back_populates="timetable_entries",
    )
    room: Mapped[Room] = relationship(
        "Room",
        back_populates="timetable_entries",
    )
    start_slot: Mapped[TimeSlot] = relationship(
        "TimeSlot",
        back_populates="timetable_entries",
    )
