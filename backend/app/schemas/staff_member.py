from typing import Any

from pydantic import BaseModel, ConfigDict, Field, field_validator

from app.models.enums import AcademicTitle, StaffType


EMAIL_PATTERN = r"^[^@\s]+@[^@\s]+\.[^@\s]+$"


def _normalize_optional_email(value: Any) -> Any:
    if isinstance(value, str):
        normalized = value.strip().lower()
        return normalized or None
    return value


class StaffMemberBase(BaseModel):
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)

    faculty_id: int = Field(..., gt=0)
    first_name: str = Field(..., min_length=1, max_length=100)
    last_name: str = Field(..., min_length=1, max_length=100)
    email: str | None = Field(default=None, max_length=255, pattern=EMAIL_PATTERN)
    academic_title: AcademicTitle | None = None
    staff_type: StaffType

    @field_validator("email", mode="before")
    @classmethod
    def normalize_email(cls, value: Any) -> Any:
        return _normalize_optional_email(value)


class StaffMemberCreate(StaffMemberBase):
    is_active: bool = True


class StaffMemberUpdate(BaseModel):
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)

    faculty_id: int | None = Field(default=None, gt=0)
    first_name: str | None = Field(default=None, min_length=1, max_length=100)
    last_name: str | None = Field(default=None, min_length=1, max_length=100)
    email: str | None = Field(default=None, max_length=255, pattern=EMAIL_PATTERN)
    academic_title: AcademicTitle | None = None
    staff_type: StaffType | None = None
    is_active: bool | None = None

    @field_validator("email", mode="before")
    @classmethod
    def normalize_email(cls, value: Any) -> Any:
        return _normalize_optional_email(value)


class StaffMemberRead(StaffMemberBase):
    model_config = ConfigDict(from_attributes=True, extra="forbid")

    id: int = Field(..., gt=0)
    is_active: bool
