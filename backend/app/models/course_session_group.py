from __future__ import annotations

from typing import TYPE_CHECKING

from app.database import Base
from sqlalchemy import ForeignKey, Index, Integer
from sqlalchemy.orm import Mapped, mapped_column, relationship

if TYPE_CHECKING:
    from app.models.course_session import CourseSession
    from app.models.student_group import StudentGroup


class CourseSessionGroup(Base):
    __tablename__ = "course_session_groups"

    __table_args__ = (
        Index(
            "ix_course_session_groups_student_group_id",
            "student_group_id",
        ),
    )

    course_session_id: Mapped[int] = mapped_column(
        Integer,
        ForeignKey("course_sessions.id"),
        primary_key=True,
    )
    student_group_id: Mapped[int] = mapped_column(
        Integer,
        ForeignKey("student_groups.id"),
        primary_key=True,
    )

    course_session: Mapped[CourseSession] = relationship(
        "CourseSession",
        back_populates="group_assignments",
    )
    student_group: Mapped[StudentGroup] = relationship(
        "StudentGroup",
        back_populates="session_assignments",
    )
