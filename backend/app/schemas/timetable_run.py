from decimal import Decimal
from typing import Literal, Self

from app.models.enums import (
    SchedulingAlgorithm,
    TimetableRunStatus,
    TimetableSourceType,
)
from pydantic import (
    AwareDatetime,
    BaseModel,
    ConfigDict,
    Field,
    JsonValue,
    model_validator,
)

ALGORITHM_REQUIRED_SOURCES = {
    TimetableSourceType.GENERATED,
    TimetableSourceType.REOPTIMIZED,
}


class TimetableRunBase(BaseModel):
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)

    academic_term_id: int = Field(..., gt=0)
    scheduling_profile_id: int = Field(..., gt=0)
    name: str = Field(..., min_length=1, max_length=150)
    source_type: TimetableSourceType
    algorithm: SchedulingAlgorithm | None = None
    parameters: dict[str, JsonValue] = Field(default_factory=dict)

    @model_validator(mode="after")
    def validate_algorithm_source(self) -> Self:
        if self.source_type in ALGORITHM_REQUIRED_SOURCES and self.algorithm is None:
            raise ValueError("generated and reoptimized runs require an algorithm")
        return self


class TimetableRunCreate(TimetableRunBase):
    """Status, scores, timestamps, and publication state are service-controlled."""


class TimetableRunUpdate(BaseModel):
    """Runs remain reproducible; only their display name is editable."""

    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)

    name: str | None = Field(default=None, min_length=1, max_length=150)

    @model_validator(mode="after")
    def require_change(self) -> Self:
        if not self.model_fields_set:
            raise ValueError("at least one field must be provided")
        if "name" in self.model_fields_set and self.name is None:
            raise ValueError("name cannot be null")
        return self


class TimetableRunRead(TimetableRunBase):
    model_config = ConfigDict(from_attributes=True, extra="forbid")

    id: int = Field(..., gt=0)
    status: TimetableRunStatus
    objective_score: Decimal | None = Field(
        default=None,
        max_digits=14,
        decimal_places=4,
    )
    hard_conflicts: int = Field(..., ge=0)
    soft_penalty: Decimal | None = Field(
        default=None,
        ge=0,
        max_digits=14,
        decimal_places=4,
    )
    execution_time_ms: int | None = Field(default=None, ge=0)
    is_published: bool
    created_at: AwareDatetime


class TimetableRunSummary(BaseModel):
    model_config = ConfigDict(
        from_attributes=True,
        extra="forbid",
        str_strip_whitespace=True,
    )

    id: int = Field(..., gt=0)
    name: str = Field(..., min_length=1, max_length=150)
    status: TimetableRunStatus
    algorithm: SchedulingAlgorithm | None = None
    objective_score: Decimal | None = Field(
        default=None,
        max_digits=14,
        decimal_places=4,
    )
    hard_conflicts: int = Field(..., ge=0)
    soft_penalty: Decimal | None = Field(
        default=None,
        ge=0,
        max_digits=14,
        decimal_places=4,
    )
    execution_time_ms: int | None = Field(default=None, ge=0)
    is_published: bool
    created_at: AwareDatetime


class TimetableRunPublishRequest(BaseModel):
    """Command body for publishing a successfully validated timetable run."""

    model_config = ConfigDict(extra="forbid")

    is_published: Literal[True] = True
