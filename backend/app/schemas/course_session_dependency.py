from typing import Self

from pydantic import BaseModel, ConfigDict, Field, model_validator

from app.models.enums import DependencyType


class CourseSessionDependencyBase(BaseModel):
    model_config = ConfigDict(extra="forbid")

    predecessor_session_id: int = Field(..., gt=0)
    successor_session_id: int = Field(..., gt=0)
    dependency_type: DependencyType
    min_gap_slots: int | None = Field(default=None, ge=0, le=32767)
    max_gap_slots: int | None = Field(default=None, ge=0, le=32767)

    @model_validator(mode="after")
    def validate_dependency(self) -> Self:
        if self.predecessor_session_id == self.successor_session_id:
            raise ValueError("a course session cannot depend on itself")

        if (
            self.min_gap_slots is not None
            and self.max_gap_slots is not None
            and self.max_gap_slots < self.min_gap_slots
        ):
            raise ValueError("max_gap_slots must be greater than or equal to min_gap_slots")

        return self


class CourseSessionDependencyCreate(CourseSessionDependencyBase):
    pass


class CourseSessionDependencyUpdate(BaseModel):
    model_config = ConfigDict(extra="forbid")

    predecessor_session_id: int | None = Field(default=None, gt=0)
    successor_session_id: int | None = Field(default=None, gt=0)
    dependency_type: DependencyType | None = None
    min_gap_slots: int | None = Field(default=None, ge=0, le=32767)
    max_gap_slots: int | None = Field(default=None, ge=0, le=32767)

    @model_validator(mode="after")
    def reject_locally_inconsistent_patch(self) -> Self:
        if (
            self.predecessor_session_id is not None
            and self.successor_session_id is not None
            and self.predecessor_session_id == self.successor_session_id
        ):
            raise ValueError("a course session cannot depend on itself")

        if (
            self.min_gap_slots is not None
            and self.max_gap_slots is not None
            and self.max_gap_slots < self.min_gap_slots
        ):
            raise ValueError("max_gap_slots must be greater than or equal to min_gap_slots")

        return self


class CourseSessionDependencyRead(CourseSessionDependencyBase):
    model_config = ConfigDict(from_attributes=True, extra="forbid")

    id: int = Field(..., gt=0)
