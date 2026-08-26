from __future__ import annotations

from typing import TYPE_CHECKING

from sqlalchemy import (
    Boolean,
    Enum as SqlEnum,
    ForeignKey,
    Identity,
    Index,
    Integer,
    String,
    UniqueConstraint,
    true,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base
from app.models.enums import AcademicTitle, StaffType

if TYPE_CHECKING:
    from app.models.faculty import Faculty
    from app.models.staff_availability import StaffAvailability
    from app.models.staff_course import StaffCourse
    from app.models.course_session_staff import CourseSessionStaff


class StaffMember(Base):
    __tablename__ = "staff_members"
    __table_args__ = (
        UniqueConstraint("email", name="uq_staff_members_email"),
        Index(
            "ix_staff_members_faculty_id",
            "faculty_id",
        ),
    )

    id: Mapped[int] = mapped_column(Integer, Identity(), primary_key=True)
    faculty_id: Mapped[int] = mapped_column(
        ForeignKey("faculties.id"),
        nullable=False,
    )
    first_name: Mapped[str] = mapped_column(String(100), nullable=False)
    last_name: Mapped[str] = mapped_column(String(100), nullable=False)
    email: Mapped[str | None] = mapped_column(String(255), nullable=True)
    academic_title: Mapped[AcademicTitle | None] = mapped_column(
        SqlEnum(
            AcademicTitle,
            name="academic_title",
            validate_strings=True,
        ),
        nullable=True,
    )
    staff_type: Mapped[StaffType] = mapped_column(
        SqlEnum(
            StaffType,
            name="staff_type",
            validate_strings=True,
        ),
        nullable=False,
    )
    is_active: Mapped[bool] = mapped_column(
        Boolean,
        nullable=False,
        default=True,
        server_default=true(),
    )

    faculty: Mapped[Faculty] = relationship(
        "Faculty",
        back_populates="staff_members",
    )
    staff_courses: Mapped[list[StaffCourse]] = relationship(
        "StaffCourse",
        back_populates="staff_member",
        lazy="selectin",
    )
    availabilities: Mapped[list[StaffAvailability]] = relationship(
        "StaffAvailability",
        back_populates="staff_member",
        lazy="selectin",
    )

    session_assignments: Mapped[list[CourseSessionStaff]] = relationship(
        "CourseSessionStaff",
        back_populates="staff_member",
        lazy="selectin",
    )
