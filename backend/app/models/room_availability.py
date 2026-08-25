from __future__ import annotations

from datetime import time
from typing import TYPE_CHECKING

from sqlalchemy import (
    CheckConstraint,
    Enum as SqlEnum,
    ForeignKey,
    Identity,
    Integer,
    SmallInteger,
    Time,
    UniqueConstraint,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base
from app.models.enums import AvailabilityType

if TYPE_CHECKING:
    from app.models.academic_term import AcademicTerm
    from app.models.room import Room


class RoomAvailability(Base):
    __tablename__ = "room_availability"
    __table_args__ = (
        UniqueConstraint(
            "room_id",
            "academic_term_id",
            "day_of_week",
            "start_time",
            "end_time",
            "availability_type",
            name="uq_room_availability_window",
        ),
        CheckConstraint(
            "day_of_week BETWEEN 1 AND 7",
            name="day_of_week_valid",
        ),
        CheckConstraint(
            "end_time > start_time",
            name="valid_time_range",
        ),
        CheckConstraint(
            "preference_weight IS NULL OR preference_weight >= 0",
            name="preference_weight_nonnegative",
        ),
    )

    id: Mapped[int] = mapped_column(Integer, Identity(), primary_key=True)
    room_id: Mapped[int] = mapped_column(
        ForeignKey("rooms.id"),
        nullable=False,
    )
    academic_term_id: Mapped[int] = mapped_column(
        ForeignKey("academic_terms.id"),
        nullable=False,
    )
    day_of_week: Mapped[int] = mapped_column(SmallInteger, nullable=False)
    start_time: Mapped[time] = mapped_column(Time, nullable=False)
    end_time: Mapped[time] = mapped_column(Time, nullable=False)
    availability_type: Mapped[AvailabilityType] = mapped_column(
        SqlEnum(
            AvailabilityType,
            name="availability_type",
            validate_strings=True,
        ),
        nullable=False,
    )
    preference_weight: Mapped[int | None] = mapped_column(
        SmallInteger,
        nullable=True,
    )

    room: Mapped[Room] = relationship(
        "Room",
        back_populates="availabilities",
    )
    academic_term: Mapped[AcademicTerm] = relationship(
        "AcademicTerm",
        back_populates="room_availabilities",
    )
