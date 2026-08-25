from __future__ import annotations

from typing import TYPE_CHECKING

from sqlalchemy import (
    Boolean,
    CheckConstraint,
    Enum as SqlEnum,
    ForeignKey,
    Identity,
    Integer,
    SmallInteger,
    String,
    UniqueConstraint,
    false,
    text,
    true,
)
from sqlalchemy.dialects.postgresql import ENUM as PgEnum
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base
from app.models.enums import ComponentType, RoomType

if TYPE_CHECKING:
    from app.models.course_offering import CourseOffering
    from app.models.course_session_dependency import CourseSessionDependency
    from app.models.course_session_group import CourseSessionGroup
    from app.models.course_session_staff import CourseSessionStaff
    from app.models.course_session_time_constraint import (
        CourseSessionTimeConstraint,
    )
    from app.models.room import Room
    from app.models.timetable_entry import TimetableEntry


class CourseSession(Base):
    __tablename__ = "course_sessions"
    __table_args__ = (
        UniqueConstraint(
            "course_offering_id",
            "name",
            name="uq_course_sessions_offering_name",
        ),
        CheckConstraint(
            "weekly_frequency > 0",
            name="weekly_frequency_positive",
        ),
        CheckConstraint(
            "duration_slots > 0",
            name="duration_slots_positive",
        ),
        CheckConstraint(
            "max_students IS NULL OR max_students > 0",
            name="max_students_positive",
        ),
    )

    id: Mapped[int] = mapped_column(Integer, Identity(), primary_key=True)
    course_offering_id: Mapped[int] = mapped_column(
        ForeignKey("course_offerings.id"),
        nullable=False,
    )
    name: Mapped[str] = mapped_column(String(150), nullable=False)
    component_type: Mapped[ComponentType] = mapped_column(
        SqlEnum(
            ComponentType,
            name="component_type",
            validate_strings=True,
        ),
        nullable=False,
    )
    weekly_frequency: Mapped[int] = mapped_column(
        SmallInteger,
        nullable=False,
        default=1,
        server_default=text("1"),
    )
    duration_slots: Mapped[int] = mapped_column(SmallInteger, nullable=False)
    max_students: Mapped[int | None] = mapped_column(Integer, nullable=True)
    required_room_type: Mapped[RoomType | None] = mapped_column(
        PgEnum(
            RoomType,
            name="room_type",
            create_type=False,
            validate_strings=True,
        ),
        nullable=True,
    )
    required_room_id: Mapped[int | None] = mapped_column(
        ForeignKey("rooms.id"),
        nullable=True,
    )
    is_splittable: Mapped[bool] = mapped_column(
        Boolean,
        nullable=False,
        default=False,
        server_default=false(),
    )
    is_active: Mapped[bool] = mapped_column(
        Boolean,
        nullable=False,
        default=True,
        server_default=true(),
    )

    course_offering: Mapped[CourseOffering] = relationship(
        "CourseOffering",
        back_populates="course_sessions",
    )
    required_room: Mapped[Room | None] = relationship(
        "Room",
        back_populates="required_by_sessions",
    )
    group_assignments: Mapped[list[CourseSessionGroup]] = relationship(
        "CourseSessionGroup",
        back_populates="course_session",
        lazy="selectin",
    )
    staff_assignments: Mapped[list[CourseSessionStaff]] = relationship(
        "CourseSessionStaff",
        back_populates="course_session",
        lazy="selectin",
    )
    time_constraints: Mapped[list[CourseSessionTimeConstraint]] = relationship(
        "CourseSessionTimeConstraint",
        back_populates="course_session",
        lazy="selectin",
    )
    outgoing_dependencies: Mapped[list[CourseSessionDependency]] = relationship(
        "CourseSessionDependency",
        foreign_keys="CourseSessionDependency.predecessor_session_id",
        back_populates="predecessor_session",
        lazy="selectin",
    )
    incoming_dependencies: Mapped[list[CourseSessionDependency]] = relationship(
        "CourseSessionDependency",
        foreign_keys="CourseSessionDependency.successor_session_id",
        back_populates="successor_session",
        lazy="selectin",
    )

    timetable_entries: Mapped[list[TimetableEntry]] = relationship(
        "TimetableEntry",
        back_populates="course_session",
        lazy="selectin",
    )