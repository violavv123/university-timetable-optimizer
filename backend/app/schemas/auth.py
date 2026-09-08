from pydantic import BaseModel, ConfigDict, Field


class AccessTokenResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    access_token: str = Field(..., min_length=1)
    token_type: str = "bearer"


class CurrentUserRead(BaseModel):
    model_config = ConfigDict(extra="forbid")

    username: str = Field(..., min_length=1, max_length=100)
