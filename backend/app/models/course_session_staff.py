from __future__ import annotations

from typing import TYPE_CHECKING

from app.database import Base
from app.models.enums import TeachingRole
from sqlalchemy import Boolean, ForeignKey, Index, Integer, false, true
from sqlalchemy import Enum as SqlEnum
from sqlalchemy.orm import Mapped, mapped_column, relationship

if TYPE_CHECKING:
    from app.models.course_session import CourseSession
    from app.models.staff_member import StaffMember


class CourseSessionStaff(Base):
    __tablename__ = "course_session_staff"

    __table_args__ = (
        Index(
            "ix_course_session_staff_staff_member_id",
            "staff_member_id",
        ),
    )

    course_session_id: Mapped[int] = mapped_column(
        Integer,
        ForeignKey("course_sessions.id"),
        primary_key=True,
    )
    staff_member_id: Mapped[int] = mapped_column(
        Integer,
        ForeignKey("staff_members.id"),
        primary_key=True,
    )
    teaching_role: Mapped[TeachingRole] = mapped_column(
        SqlEnum(
            TeachingRole,
            name="teaching_role",
            validate_strings=True,
        ),
        nullable=False,
    )
    is_primary: Mapped[bool] = mapped_column(
        Boolean,
        nullable=False,
        default=False,
        server_default=false(),
    )
    is_fixed: Mapped[bool] = mapped_column(
        Boolean,
        nullable=False,
        default=True,
        server_default=true(),
    )

    course_session: Mapped[CourseSession] = relationship(
        "CourseSession",
        back_populates="staff_assignments",
    )
    staff_member: Mapped[StaffMember] = relationship(
        "StaffMember",
        back_populates="session_assignments",
    )
