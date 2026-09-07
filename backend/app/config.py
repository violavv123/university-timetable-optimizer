from pathlib import Path

from pydantic import Field, SecretStr
from pydantic_settings import BaseSettings, SettingsConfigDict

BACKEND_DIR = Path(__file__).resolve().parent.parent


class Settings(BaseSettings):
    database_url: str
    frontend_url: str = "http://localhost:5173"
    app_name: str = "University Timetable Optimizer"
    debug: bool = False

    admin_username: str = Field(min_length=1, max_length=100)
    admin_password_hash: SecretStr
    jwt_secret_key: SecretStr
    access_token_expire_minutes: int = Field(default=60, gt=0)

    model_config = SettingsConfigDict(
        env_file=BACKEND_DIR / ".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )


# noinspection PyArgumentList
settings = Settings()
