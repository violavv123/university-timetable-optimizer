from datetime import date
from typing import Self

from pydantic import BaseModel, ConfigDict, Field, model_validator

from app.models.enums import TermType


class AcademicTermBase(BaseModel):
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)

    academic_year_id: int = Field(..., gt=0)
    name: str = Field(..., min_length=1, max_length=100)
    term_type: TermType
    start_date: date
    end_date: date

    @model_validator(mode="after")
    def validate_date_range(self) -> Self:
        if self.end_date <= self.start_date:
            raise ValueError("end_date must be after start_date")
        return self


class AcademicTermCreate(AcademicTermBase):
    is_active: bool = True


class AcademicTermUpdate(BaseModel):
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)

    academic_year_id: int | None = Field(default=None, gt=0)
    name: str | None = Field(default=None, min_length=1, max_length=100)
    term_type: TermType | None = None
    start_date: date | None = None
    end_date: date | None = None
    is_active: bool | None = None

    @model_validator(mode="after")
    def validate_supplied_date_range(self) -> Self:
        if (
            self.start_date is not None
            and self.end_date is not None
            and self.end_date <= self.start_date
        ):
            raise ValueError("end_date must be after start_date")
        return self


class AcademicTermRead(AcademicTermBase):
    model_config = ConfigDict(from_attributes=True, extra="forbid")

    id: int = Field(..., gt=0)
    is_active: bool
