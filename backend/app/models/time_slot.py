from __future__ import annotations

from datetime import time
from typing import TYPE_CHECKING

from app.database import Base
from sqlalchemy import (
    Boolean,
    CheckConstraint,
    ForeignKey,
    Identity,
    Integer,
    SmallInteger,
    Time,
    UniqueConstraint,
    true,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

if TYPE_CHECKING:
    from app.models.scheduling_profile import SchedulingProfile
    from app.models.timetable_entry import TimetableEntry


class TimeSlot(Base):
    __tablename__ = "time_slots"
    __table_args__ = (
        UniqueConstraint(
            "scheduling_profile_id",
            "day_of_week",
            "slot_index",
            name="uq_time_slots_profile_day_index",
        ),
        UniqueConstraint(
            "scheduling_profile_id",
            "day_of_week",
            "start_time",
            name="uq_time_slots_profile_day_start",
        ),
        CheckConstraint(
            "day_of_week BETWEEN 1 AND 7",
            name="day_of_week_valid",
        ),
        CheckConstraint("slot_index >= 0", name="slot_index_nonnegative"),
        CheckConstraint("end_time > start_time", name="valid_time_range"),
    )

    id: Mapped[int] = mapped_column(Integer, Identity(), primary_key=True)
    scheduling_profile_id: Mapped[int] = mapped_column(
        ForeignKey("scheduling_profiles.id"),
        nullable=False,
    )
    day_of_week: Mapped[int] = mapped_column(SmallInteger, nullable=False)
    slot_index: Mapped[int] = mapped_column(SmallInteger, nullable=False)
    start_time: Mapped[time] = mapped_column(Time, nullable=False)
    end_time: Mapped[time] = mapped_column(Time, nullable=False)
    is_active: Mapped[bool] = mapped_column(
        Boolean,
        nullable=False,
        default=True,
        server_default=true(),
    )

    scheduling_profile: Mapped[SchedulingProfile] = relationship(
        "SchedulingProfile",
        back_populates="time_slots",
    )

    timetable_entries: Mapped[list[TimetableEntry]] = relationship(
        "TimetableEntry",
        back_populates="start_slot",
        lazy="selectin",
    )
