from typing import Generic, TypeVar

from pydantic import BaseModel, ConfigDict, Field, computed_field


T = TypeVar("T")


class MessageResponse(BaseModel):
    """Response returned after a successful operation without entity data."""

    model_config = ConfigDict(
        extra="forbid",
        str_strip_whitespace=True,
    )

    message: str = Field(
        ...,
        min_length=1,
        examples=["Resource deleted successfully."],
    )


class PaginationParams(BaseModel):
    """Reusable query parameters for paginated list endpoints."""

    model_config = ConfigDict(extra="forbid")

    page: int = Field(
        default=1,
        ge=1,
        description="Requested page number.",
    )
    page_size: int = Field(
        default=20,
        ge=1,
        le=100,
        description="Maximum number of records returned per page.",
    )

    @property
    def offset(self) -> int:
        """Number of database records to skip."""

        return (self.page - 1) * self.page_size


class PaginatedResponse(BaseModel, Generic[T]):
    """Generic response returned by paginated list endpoints."""

    model_config = ConfigDict(extra="forbid")

    items: list[T] = Field(default_factory=list)
    total: int = Field(
        ...,
        ge=0,
        description="Total number of matching records.",
    )
    page: int = Field(
        ...,
        ge=1,
        description="Current page number.",
    )
    page_size: int = Field(
        ...,
        ge=1,
        description="Number of records requested per page.",
    )

    @computed_field
    @property
    def total_pages(self) -> int:
        """Total number of available pages."""

        if self.total == 0:
            return 0

        return (self.total + self.page_size - 1) // self.page_size


class ValidationErrorDetail(BaseModel):
    """Description of one request-validation error."""

    model_config = ConfigDict(extra="ignore")

    loc: list[str | int] = Field(
        default_factory=list,
        description="Location of the invalid field.",
        examples=[["body", "expected_students"]],
    )
    msg: str = Field(
        ...,
        description="Human-readable validation message.",
        examples=["Input should be greater than 0."],
    )
    type: str = Field(
        ...,
        description="Pydantic validation-error code.",
        examples=["greater_than"],
    )


class ValidationErrorResponse(BaseModel):
    """Response containing all request-validation errors."""

    model_config = ConfigDict(extra="forbid")

    detail: list[ValidationErrorDetail] = Field(default_factory=list)


__all__ = [
    "MessageResponse",
    "PaginationParams",
    "PaginatedResponse",
    "ValidationErrorDetail",
    "ValidationErrorResponse",
]