from __future__ import annotations

from typing import TYPE_CHECKING

from sqlalchemy import (
    CheckConstraint,
    Enum as SqlEnum,
    ForeignKey,
    Identity,
    Integer,
    SmallInteger,
    UniqueConstraint,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base
from app.models.enums import DependencyType

if TYPE_CHECKING:
    from app.models.course_session import CourseSession


class CourseSessionDependency(Base):
    __tablename__ = "course_session_dependencies"
    __table_args__ = (
        UniqueConstraint(
            "predecessor_session_id",
            "successor_session_id",
            "dependency_type",
            name="uq_course_session_dependencies_pair_type",
        ),
        CheckConstraint(
            "predecessor_session_id <> successor_session_id",
            name="sessions_must_differ",
        ),
        CheckConstraint(
            "min_gap_slots IS NULL OR min_gap_slots >= 0",
            name="min_gap_slots_nonnegative",
        ),
        CheckConstraint(
            "max_gap_slots IS NULL OR max_gap_slots >= 0",
            name="max_gap_slots_nonnegative",
        ),
        CheckConstraint(
            "min_gap_slots IS NULL OR max_gap_slots IS NULL "
            "OR max_gap_slots >= min_gap_slots",
            name="gap_range_valid",
        ),
    )

    id: Mapped[int] = mapped_column(Integer, Identity(), primary_key=True)
    predecessor_session_id: Mapped[int] = mapped_column(
        ForeignKey("course_sessions.id"),
        nullable=False,
    )
    successor_session_id: Mapped[int] = mapped_column(
        ForeignKey("course_sessions.id"),
        nullable=False,
    )
    dependency_type: Mapped[DependencyType] = mapped_column(
        SqlEnum(
            DependencyType,
            name="dependency_type",
            validate_strings=True,
        ),
        nullable=False,
    )
    min_gap_slots: Mapped[int | None] = mapped_column(
        SmallInteger,
        nullable=True,
    )
    max_gap_slots: Mapped[int | None] = mapped_column(
        SmallInteger,
        nullable=True,
    )

    predecessor_session: Mapped[CourseSession] = relationship(
        "CourseSession",
        foreign_keys=[predecessor_session_id],
        back_populates="outgoing_dependencies",
    )
    successor_session: Mapped[CourseSession] = relationship(
        "CourseSession",
        foreign_keys=[successor_session_id],
        back_populates="incoming_dependencies",
    )
