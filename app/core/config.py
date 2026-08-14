"""
Application configuration for NXPI Monolith.
All settings are loaded from environment variables via Pydantic BaseSettings.
"""

from functools import lru_cache
from typing import Literal

from pydantic import field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    # ─── Application ──────────────────────────────────────────────────────────
    APP_ENV: Literal["local", "staging", "production"] = "local"
    APP_NAME: str = "nxpi-backend"
    APP_PORT: int = 8000
    APP_DEBUG: bool = False
    APP_VERSION: str = "1.0.0"

    # ─── Database ─────────────────────────────────────────────────────────────
    DATABASE_URL: str
    DATABASE_SCHEMA: str = "public"
    DATABASE_POOL_SIZE: int = 10
    DATABASE_MAX_OVERFLOW: int = 20

    # ─── JWT ──────────────────────────────────────────────────────────────────
    JWT_SECRET: str
    JWT_ALGORITHM: str = "HS256"
    JWT_ACCESS_TOKEN_EXPIRE_MINUTES: int = 15
    JWT_REFRESH_TOKEN_EXPIRE_DAYS: int = 7

    # ─── OTP ──────────────────────────────────────────────────────────────────
    OTP_RATE_LIMIT_MAX: int = 10
    OTP_RATE_LIMIT_WINDOW_MINUTES: int = 10
    OTP_EXPIRE_MINUTES: int = 5
    OTP_MAX_ATTEMPTS: int = 5
    DISABLE_OTP_VERIFICATION: bool = True

    # ─── Email (Resend) ───────────────────────────────────────────────────────
    RESEND_API_KEY: str = ""
    FROM_EMAIL: str = "noreply@negentrophi.com"
    FROM_NAME: str = "Negentrophi"

    # ─── Admin Credentials ──────────────────────────────────────────────────
    ADMIN_EMAIL: str
    ADMIN_PASSWORD: str

    # ─── Google Calendar API (Service Account) ─────────────────────────────
    GOOGLE_CALENDAR_CLIENT_EMAIL: str = ""
    GOOGLE_CALENDAR_PRIVATE_KEY: str = ""
    GOOGLE_CALENDAR_ID: str = ""

    # ─── Google Meet (fixed consultation room) ───────────────────────────────
    GOOGLE_MEET_DEFAULT_ROOM: str = ""

    # ─── Google OAuth2 (User-level, for real Google Meet links) ────────────
    GOOGLE_OAUTH_CLIENT_ID: str = ""
    GOOGLE_OAUTH_CLIENT_SECRET: str = ""
    GOOGLE_OAUTH_REFRESH_TOKEN: str = ""

    # ─── Observability ────────────────────────────────────────────────────────
    SENTRY_DSN: str = ""
    LOG_LEVEL: str = "INFO"

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=True,
        extra="ignore",
    )

    @field_validator("DATABASE_URL")
    @classmethod
    def validate_database_url(cls, v: str) -> str:
        if not v.startswith("postgresql"):
            raise ValueError("DATABASE_URL must be a PostgreSQL connection string")
        return v

    @field_validator("JWT_SECRET")
    @classmethod
    def validate_jwt_secret(cls, v: str) -> str:
        if len(v) < 32:
            raise ValueError("JWT_SECRET must be at least 32 characters long")
        return v


@lru_cache
def get_settings() -> Settings:
    return Settings()


settings: Settings = get_settings()
