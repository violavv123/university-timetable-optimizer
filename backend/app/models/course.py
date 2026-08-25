from __future__ import annotations

from typing import TYPE_CHECKING

from sqlalchemy import Boolean, Identity, Integer, String, UniqueConstraint, true
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base

if TYPE_CHECKING:
    from app.models.curriculum_course import CurriculumCourse
    from app.models.staff_course import StaffCourse


class Course(Base):
    __tablename__ = "courses"
    __table_args__ = (
        UniqueConstraint("code", name="uq_courses_code"),
    )

    id: Mapped[int] = mapped_column(Integer, Identity(), primary_key=True)
    code: Mapped[str] = mapped_column(String(30), nullable=False)
    name: Mapped[str] = mapped_column(String(200), nullable=False)
    is_active: Mapped[bool] = mapped_column(
        Boolean,
        nullable=False,
        default=True,
        server_default=true(),
    )

    curriculum_courses: Mapped[list[CurriculumCourse]] = relationship(
        "CurriculumCourse",
        back_populates="course",
        lazy="selectin",
    )

    staff_courses: Mapped[list[StaffCourse]] = relationship(
        "StaffCourse",
        back_populates="course",
        lazy="selectin",
    )