from __future__ import annotations

from typing import TYPE_CHECKING

from app.database import Base
from sqlalchemy import (
    Boolean,
    CheckConstraint,
    ForeignKey,
    Identity,
    Integer,
    UniqueConstraint,
    false,
    true,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

if TYPE_CHECKING:
    from app.models.course import Course
    from app.models.staff_member import StaffMember


class StaffCourse(Base):
    __tablename__ = "staff_courses"
    __table_args__ = (
        UniqueConstraint(
            "staff_member_id",
            "course_id",
            name="uq_staff_courses_staff_course",
        ),
        CheckConstraint(
            "can_lecture = true OR can_assist = true",
            name="teaching_capability_required",
        ),
    )

    id: Mapped[int] = mapped_column(Integer, Identity(), primary_key=True)
    staff_member_id: Mapped[int] = mapped_column(
        ForeignKey("staff_members.id"),
        nullable=False,
    )
    course_id: Mapped[int] = mapped_column(
        ForeignKey("courses.id"),
        nullable=False,
    )
    can_lecture: Mapped[bool] = mapped_column(
        Boolean,
        nullable=False,
        default=False,
        server_default=false(),
    )
    can_assist: Mapped[bool] = mapped_column(
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

    staff_member: Mapped[StaffMember] = relationship(
        "StaffMember",
        back_populates="staff_courses",
    )
    course: Mapped[Course] = relationship(
        "Course",
        back_populates="staff_courses",
    )
