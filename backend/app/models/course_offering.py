from __future__ import annotations

from typing import TYPE_CHECKING

from sqlalchemy import (
    CheckConstraint,
    Enum as SqlEnum,
    ForeignKey,
    Identity,
    Integer,
    UniqueConstraint,
    text,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base
from app.models.enums import CourseOfferingStatus

if TYPE_CHECKING:
    from app.models.academic_term import AcademicTerm
    from app.models.course_session import CourseSession
    from app.models.curriculum_course import CurriculumCourse


class CourseOffering(Base):
    __tablename__ = "course_offerings"
    __table_args__ = (
        UniqueConstraint(
            "curriculum_course_id",
            "academic_term_id",
            name="uq_course_offerings_curriculum_term",
        ),
        CheckConstraint(
            "expected_students IS NULL OR expected_students > 0",
            name="expected_students_positive",
        ),
    )

    id: Mapped[int] = mapped_column(Integer, Identity(), primary_key=True)
    curriculum_course_id: Mapped[int] = mapped_column(
        ForeignKey("curriculum_courses.id"),
        nullable=False,
    )
    academic_term_id: Mapped[int] = mapped_column(
        ForeignKey("academic_terms.id"),
        nullable=False,
    )
    expected_students: Mapped[int | None] = mapped_column(Integer, nullable=True)
    status: Mapped[CourseOfferingStatus] = mapped_column(
        SqlEnum(
            CourseOfferingStatus,
            name="course_offering_status",
            validate_strings=True,
        ),
        nullable=False,
        default=CourseOfferingStatus.DRAFT,
        server_default=text("'DRAFT'"),
    )

    curriculum_course: Mapped[CurriculumCourse] = relationship(
        "CurriculumCourse",
        back_populates="course_offerings",
    )
    academic_term: Mapped[AcademicTerm] = relationship(
        "AcademicTerm",
        back_populates="course_offerings",
    )
    course_sessions: Mapped[list[CourseSession]] = relationship(
        "CourseSession",
        back_populates="course_offering",
        lazy="selectin",
    )
