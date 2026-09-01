from __future__ import annotations

from datetime import datetime
from decimal import Decimal
from typing import TYPE_CHECKING, Any

from app.database import Base
from app.models.enums import (
    SchedulingAlgorithm,
    TimetableRunStatus,
    TimetableSourceType,
)
from sqlalchemy import (
    BigInteger,
    Boolean,
    CheckConstraint,
    DateTime,
    ForeignKey,
    Identity,
    Index,
    Integer,
    Numeric,
    String,
    UniqueConstraint,
    false,
    func,
    text,
)
from sqlalchemy import (
    Enum as SqlEnum,
)
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column, relationship

if TYPE_CHECKING:
    from app.models.academic_term import AcademicTerm
    from app.models.scheduling_profile import SchedulingProfile
    from app.models.timetable_entry import TimetableEntry


class TimetableRun(Base):
    __tablename__ = "timetable_runs"
    __table_args__ = (
        UniqueConstraint(
            "academic_term_id",
            "scheduling_profile_id",
            "name",
            name="uq_timetable_runs_term_profile_name",
        ),
        CheckConstraint(
            "hard_conflicts >= 0",
            name="hard_conflicts_nonnegative",
        ),
        CheckConstraint(
            "soft_penalty IS NULL OR soft_penalty >= 0",
            name="soft_penalty_nonnegative",
        ),
        CheckConstraint(
            "execution_time_ms IS NULL OR execution_time_ms >= 0",
            name="execution_time_ms_nonnegative",
        ),
        Index(
            "uq_published_timetable",
            "academic_term_id",
            "scheduling_profile_id",
            unique=True,
            postgresql_where=text("is_published = true"),
        ),
    )

    id: Mapped[int] = mapped_column(Integer, Identity(), primary_key=True)
    academic_term_id: Mapped[int] = mapped_column(
        ForeignKey("academic_terms.id"),
        nullable=False,
    )
    scheduling_profile_id: Mapped[int] = mapped_column(
        ForeignKey("scheduling_profiles.id"),
        nullable=False,
    )
    name: Mapped[str] = mapped_column(String(150), nullable=False)
    source_type: Mapped[TimetableSourceType] = mapped_column(
        SqlEnum(
            TimetableSourceType,
            name="timetable_source_type",
            validate_strings=True,
        ),
        nullable=False,
    )
    algorithm: Mapped[SchedulingAlgorithm | None] = mapped_column(
        SqlEnum(
            SchedulingAlgorithm,
            name="scheduling_algorithm",
            validate_strings=True,
        ),
        nullable=True,
    )
    status: Mapped[TimetableRunStatus] = mapped_column(
        SqlEnum(
            TimetableRunStatus,
            name="timetable_run_status",
            validate_strings=True,
        ),
        nullable=False,
        default=TimetableRunStatus.PENDING,
        server_default=text("'PENDING'"),
    )
    parameters: Mapped[dict[str, Any]] = mapped_column(
        JSONB,
        nullable=False,
        default=dict,
        server_default=text("'{}'::jsonb"),
    )
    objective_score: Mapped[Decimal | None] = mapped_column(
        Numeric(14, 4),
        nullable=True,
    )
    hard_conflicts: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
        default=0,
        server_default=text("0"),
    )
    soft_penalty: Mapped[Decimal | None] = mapped_column(
        Numeric(14, 4),
        nullable=True,
    )
    execution_time_ms: Mapped[int | None] = mapped_column(
        BigInteger,
        nullable=True,
    )
    is_published: Mapped[bool] = mapped_column(
        Boolean,
        nullable=False,
        default=False,
        server_default=false(),
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        server_default=func.now(),
    )

    academic_term: Mapped[AcademicTerm] = relationship(
        "AcademicTerm",
        back_populates="timetable_runs",
    )
    scheduling_profile: Mapped[SchedulingProfile] = relationship(
        "SchedulingProfile",
        back_populates="timetable_runs",
    )
    timetable_entries: Mapped[list[TimetableEntry]] = relationship(
        "TimetableEntry",
        back_populates="timetable_run",
        lazy="selectin",
    )
