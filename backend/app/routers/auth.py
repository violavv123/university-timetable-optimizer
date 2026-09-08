from typing import Annotated

from app.core.exceptions import AuthenticationError
from app.core.security import (
    authenticate_admin,
    create_access_token,
    require_admin,
)
from app.schemas.auth import AccessTokenResponse, CurrentUserRead
from fastapi import APIRouter, Depends
from fastapi.security import OAuth2PasswordRequestForm

router = APIRouter(prefix="/auth", tags=["Authentication"])

LoginForm = Annotated[OAuth2PasswordRequestForm, Depends()]
CurrentAdmin = Annotated[CurrentUserRead, Depends(require_admin)]


@router.post("/token", response_model=AccessTokenResponse)
def login(form: LoginForm) -> AccessTokenResponse:
    if not authenticate_admin(form.username, form.password):
        raise AuthenticationError("Incorrect username or password.")

    return AccessTokenResponse(
        access_token=create_access_token(form.username),
    )


@router.get("/me", response_model=CurrentUserRead)
def get_current_user(current_admin: CurrentAdmin) -> CurrentUserRead:
    return current_admin


__all__ = ["router"]
