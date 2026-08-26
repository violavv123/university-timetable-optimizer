from pydantic import BaseModel, ConfigDict, Field, JsonValue


class ErrorResponse(BaseModel):
    """Stable error envelope returned by every application exception handler."""

    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)

    code: str = Field(
        ...,
        min_length=1,
        max_length=100,
        pattern=r"^[a-z][a-z0-9_]*$",
        examples=["resource_not_found"],
    )
    message: str = Field(..., min_length=1)
    details: JsonValue | None = None
