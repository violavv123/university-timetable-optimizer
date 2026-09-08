from datetime import UTC, datetime, timedelta
from secrets import compare_digest
from typing import Annotated

import jwt
from app.config import settings
from app.core.exceptions import AuthenticationError
from app.schemas.auth import CurrentUserRead
from fastapi import Depends
from fastapi.security import OAuth2PasswordBearer
from jwt.exceptions import InvalidTokenError
from pwdlib import PasswordHash

JWT_ALGORITHM = "HS256"

password_hash = PasswordHash.recommended()

oauth2_scheme = OAuth2PasswordBearer(
    tokenUrl="/api/v1/auth/token",
    auto_error=False,
)

OptionalToken = Annotated[str | None, Depends(oauth2_scheme)]


def authenticate_admin(username: str, password: str) -> bool:
    expected_username = settings.admin_username
    stored_hash = settings.admin_password_hash.get_secret_value()

    username_is_valid = compare_digest(username, expected_username)
    password_is_valid = password_hash.verify(password, stored_hash)

    return username_is_valid and password_is_valid


def create_access_token(username: str) -> str:
    now = datetime.now(UTC)
    expires_at = now + timedelta(minutes=settings.access_token_expire_minutes)

    return jwt.encode(
        {
            "sub": username,
            "iat": now,
            "exp": expires_at,
        },
        settings.jwt_secret_key.get_secret_value(),
        algorithm=JWT_ALGORITHM,
    )


def require_admin(token: OptionalToken) -> CurrentUserRead:
    if token is None:
        raise AuthenticationError()

    try:
        payload = jwt.decode(
            token,
            settings.jwt_secret_key.get_secret_value(),
            algorithms=[JWT_ALGORITHM],
        )
        username = payload.get("sub")
    except InvalidTokenError as error:
        raise AuthenticationError("The access token is invalid or expired.") from error

    if not isinstance(username, str) or not compare_digest(username, settings.admin_username):
        raise AuthenticationError("The access token is invalid or expired.")

    return CurrentUserRead(username=username)
