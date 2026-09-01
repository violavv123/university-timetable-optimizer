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
    from app.models.faculty import Faculty
    from app.models.time_slot import TimeSlot
    from app.models.timetable_run import TimetableRun


class SchedulingProfile(Base):
    __tablename__ = "scheduling_profiles"
    __table_args__ = (
        UniqueConstraint(
            "faculty_id",
            "name",
            name="uq_scheduling_profiles_faculty_name",
        ),
        CheckConstraint("slot_minutes > 0", name="slot_minutes_positive"),
        CheckConstraint(
            "max_lecture_students > 0",
            name="max_lecture_students_positive",
        ),
        CheckConstraint(
            "max_numerical_students > 0",
            name="max_numerical_students_positive",
        ),
        CheckConstraint(
            "max_lab_students > 0",
            name="max_lab_students_positive",
        ),
        CheckConstraint(
            "preferred_room_weight >= 0",
            name="preferred_room_weight_nonnegative",
        ),
        CheckConstraint(
            "historical_room_weight >= 0",
            name="historical_room_weight_nonnegative",
        ),
        CheckConstraint(
            "student_gap_weight >= 0",
            name="student_gap_weight_nonnegative",
        ),
        CheckConstraint(
            "staff_gap_weight >= 0",
            name="staff_gap_weight_nonnegative",
        ),
        CheckConstraint(
            "late_hour_weight >= 0",
            name="late_hour_weight_nonnegative",
        ),
    )

    id: Mapped[int] = mapped_column(Integer, Identity(), primary_key=True)
    faculty_id: Mapped[int] = mapped_column(
        ForeignKey("faculties.id"),
        nullable=False,
    )
    name: Mapped[str] = mapped_column(String(150), nullable=False)
    slot_minutes: Mapped[int] = mapped_column(
        SmallInteger,
        nullable=False,
        default=45,
        server_default=text("45"),
    )
    max_lecture_students: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
        default=60,
        server_default=text("60"),
    )
    max_numerical_students: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
        default=40,
        server_default=text("40"),
    )
    max_lab_students: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
        default=40,
        server_default=text("40"),
    )
    preferred_room_weight: Mapped[int] = mapped_column(
        SmallInteger,
        nullable=False,
        default=1,
        server_default=text("1"),
    )
    historical_room_weight: Mapped[int] = mapped_column(
        SmallInteger,
        nullable=False,
        default=1,
        server_default=text("1"),
    )
    student_gap_weight: Mapped[int] = mapped_column(
        SmallInteger,
        nullable=False,
        default=1,
        server_default=text("1"),
    )
    staff_gap_weight: Mapped[int] = mapped_column(
        SmallInteger,
        nullable=False,
        default=1,
        server_default=text("1"),
    )
    late_hour_weight: Mapped[int] = mapped_column(
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

    faculty: Mapped[Faculty] = relationship(
        "Faculty",
        back_populates="scheduling_profiles",
    )
    time_slots: Mapped[list[TimeSlot]] = relationship(
        "TimeSlot",
        back_populates="scheduling_profile",
        lazy="selectin",
    )

    timetable_runs: Mapped[list[TimetableRun]] = relationship(
        "TimetableRun",
        back_populates="scheduling_profile",
        lazy="selectin",
    )
