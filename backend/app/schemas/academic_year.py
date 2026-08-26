from datetime import date
from typing import Literal, Self

from pydantic import BaseModel, ConfigDict, Field, model_validator


ACADEMIC_YEAR_PATTERN = r"^\d{4}/\d{4}$"


class AcademicYearBase(BaseModel):
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)

    name: str = Field(
        ...,
        min_length=9,
        max_length=20,
        pattern=ACADEMIC_YEAR_PATTERN,
        examples=["2026/2027"],
    )
    start_date: date
    end_date: date

    @model_validator(mode="after")
    def validate_academic_year(self) -> Self:
        if self.end_date <= self.start_date:
            raise ValueError("end_date must be after start_date")

        first_year, second_year = (int(value) for value in self.name.split("/"))
        if second_year != first_year + 1:
            raise ValueError("academic year name must contain consecutive years")

        return self


class AcademicYearCreate(AcademicYearBase):
    """New years are non-current until the set-current operation succeeds."""


class AcademicYearUpdate(BaseModel):
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)

    name: str | None = Field(
        default=None,
        min_length=9,
        max_length=20,
        pattern=ACADEMIC_YEAR_PATTERN,
    )
    start_date: date | None = None
    end_date: date | None = None

    @model_validator(mode="after")
    def validate_supplied_values(self) -> Self:
        if (
            self.start_date is not None
            and self.end_date is not None
            and self.end_date <= self.start_date
        ):
            raise ValueError("end_date must be after start_date")

        if self.name is not None:
            first_year, second_year = (int(value) for value in self.name.split("/"))
            if second_year != first_year + 1:
                raise ValueError("academic year name must contain consecutive years")

        return self


class AcademicYearRead(AcademicYearBase):
    model_config = ConfigDict(from_attributes=True, extra="forbid")

    id: int = Field(..., gt=0)
    is_current: bool


class AcademicYearSetCurrent(BaseModel):
    """Command body for the transactional set-current endpoint."""

    model_config = ConfigDict(extra="forbid")

    is_current: Literal[True] = True
