from __future__ import annotations

from typing import TYPE_CHECKING

from sqlalchemy import (
    CheckConstraint,
    Enum as SqlEnum,
    ForeignKey,
    Identity,
    Integer,
    String,
    UniqueConstraint,
    text,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base
from app.models.enums import RoomStatus, RoomType

if TYPE_CHECKING:
    from app.models.faculty import Faculty
    from app.models.program_room_preference import ProgramRoomPreference
    from app.models.room_availability import RoomAvailability
    from app.models.course_session import CourseSession
    from app.models.timetable_entry import TimetableEntry


class Room(Base):
    __tablename__ = "rooms"
    __table_args__ = (
        UniqueConstraint(
            "faculty_id",
            "code",
            name="uq_rooms_faculty_code",
        ),
        CheckConstraint("capacity > 0", name="capacity_positive"),
    )

    id: Mapped[int] = mapped_column(Integer, Identity(), primary_key=True)
    faculty_id: Mapped[int] = mapped_column(
        ForeignKey("faculties.id"),
        nullable=False,
    )
    code: Mapped[str] = mapped_column(String(30), nullable=False)
    name: Mapped[str] = mapped_column(String(150), nullable=False)
    capacity: Mapped[int] = mapped_column(Integer, nullable=False)
    room_type: Mapped[RoomType] = mapped_column(
        SqlEnum(
            RoomType,
            name="room_type",
            validate_strings=True,
        ),
        nullable=False,
    )
    status: Mapped[RoomStatus] = mapped_column(
        SqlEnum(
            RoomStatus,
            name="room_status",
            validate_strings=True,
        ),
        nullable=False,
        default=RoomStatus.ACTIVE,
        server_default=text("'ACTIVE'"),
    )

    faculty: Mapped[Faculty] = relationship(
        "Faculty",
        back_populates="rooms",
    )
    availabilities: Mapped[list[RoomAvailability]] = relationship(
        "RoomAvailability",
        back_populates="room",
        lazy="selectin",
    )
    program_preferences: Mapped[list[ProgramRoomPreference]] = relationship(
        "ProgramRoomPreference",
        back_populates="room",
        lazy="selectin",
    )

    required_by_sessions: Mapped[list[CourseSession]] = relationship(
        "CourseSession",
        back_populates="required_room",
        lazy="selectin",
    )

    timetable_entries: Mapped[list[TimetableEntry]] = relationship(
        "TimetableEntry",
        back_populates="room",
        lazy="selectin",
    )
