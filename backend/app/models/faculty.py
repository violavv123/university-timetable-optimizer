from __future__ import annotations

from typing import TYPE_CHECKING

from app.database import Base
from sqlalchemy import Boolean, Integer, String, UniqueConstraint, true
from sqlalchemy.orm import Mapped, mapped_column, relationship

if TYPE_CHECKING:
    from app.models.room import Room
    from app.models.scheduling_profile import SchedulingProfile
    from app.models.staff_member import StaffMember
    from app.models.study_program import StudyProgram


class Faculty(Base):
    __tablename__ = "faculties"
    __table_args__ = (UniqueConstraint("code", name="uq_faculties_code"),)

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    code: Mapped[str] = mapped_column(String(30), nullable=False)
    name: Mapped[str] = mapped_column(String(150), nullable=False)
    is_active: Mapped[bool] = mapped_column(
        Boolean,
        nullable=False,
        default=True,
        server_default=true(),
    )

    study_programs: Mapped[list[StudyProgram]] = relationship(
        "StudyProgram",
        back_populates="faculty",
        lazy="selectin",
    )

    staff_members: Mapped[list[StaffMember]] = relationship(
        "StaffMember",
        back_populates="faculty",
        lazy="selectin",
    )

    rooms: Mapped[list[Room]] = relationship(
        "Room",
        back_populates="faculty",
        lazy="selectin",
    )

    scheduling_profiles: Mapped[list[SchedulingProfile]] = relationship(
        "SchedulingProfile",
        back_populates="faculty",
        lazy="selectin",
    )
