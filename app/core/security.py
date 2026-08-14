"""
Security utilities: JWT signing/verification, native bcrypt hashing, OTP generation.
"""

import logging
import secrets
import string
from datetime import datetime, timedelta, timezone

import bcrypt
from jose import JWTError, jwt

from app.core.config import settings

logger = logging.getLogger(__name__)


# ─── Password Hashing ─────────────────────────────────────────────────────────

def hash_password(plain_password: str) -> str:
    """Hash a plain-text password with bcrypt."""
    try:
        pw_bytes = plain_password.encode("utf-8")[:72]
        salt = bcrypt.gensalt()
        return bcrypt.hashpw(pw_bytes, salt).decode("utf-8")
    except Exception as exc:
        logger.error(f"Password hashing failed: {exc}")
        raise RuntimeError("Failed to hash password") from exc


def verify_password(plain_password: str, hashed_password: str) -> bool:
    """Verify a plain-text password against a bcrypt hash."""
    try:
        pw_bytes = plain_password.encode("utf-8")[:72]
        hash_bytes = hashed_password.encode("utf-8")
        return bcrypt.checkpw(pw_bytes, hash_bytes)
    except Exception as exc:
        logger.error(f"Password verification error: {exc}")
        return False


# ─── OTP Utilities ────────────────────────────────────────────────────────────

def generate_otp(length: int = 6) -> str:
    """Generate a cryptographically secure numeric OTP."""
    try:
        return "".join(secrets.choice(string.digits) for _ in range(length))
    except Exception as exc:
        logger.error(f"OTP generation failed: {exc}")
        raise RuntimeError("Failed to generate OTP") from exc


def hash_otp(plain_otp: str) -> str:
    """Hash an OTP with bcrypt for secure storage."""
    try:
        pw_bytes = plain_otp.encode("utf-8")[:72]
        salt = bcrypt.gensalt()
        return bcrypt.hashpw(pw_bytes, salt).decode("utf-8")
    except Exception as exc:
        logger.error(f"OTP hashing failed: {exc}")
        raise RuntimeError("Failed to hash OTP") from exc


def verify_otp(plain_otp: str, hashed_otp: str) -> bool:
    """Verify a plain OTP against its bcrypt hash."""
    try:
        pw_bytes = plain_otp.encode("utf-8")[:72]
        hash_bytes = hashed_otp.encode("utf-8")
        return bcrypt.checkpw(pw_bytes, hash_bytes)
    except Exception as exc:
        logger.error(f"OTP verification error: {exc}")
        return False


# ─── JWT ──────────────────────────────────────────────────────────────────────

def create_access_token(payload: dict) -> str:
    try:
        expire = datetime.now(timezone.utc) + timedelta(
            minutes=settings.JWT_ACCESS_TOKEN_EXPIRE_MINUTES
        )
        data = {**payload, "exp": expire, "type": "access"}
        return jwt.encode(data, settings.JWT_SECRET, algorithm=settings.JWT_ALGORITHM)
    except Exception as exc:
        logger.error(f"Access token creation failed: {exc}")
        raise RuntimeError("Failed to create access token") from exc


def create_refresh_token(payload: dict) -> tuple[str, datetime]:
    try:
        expire = datetime.now(timezone.utc) + timedelta(
            days=settings.JWT_REFRESH_TOKEN_EXPIRE_DAYS
        )
        data = {**payload, "exp": expire, "type": "refresh"}
        token = jwt.encode(data, settings.JWT_SECRET, algorithm=settings.JWT_ALGORITHM)
        return token, expire
    except Exception as exc:
        logger.error(f"Refresh token creation failed: {exc}")
        raise RuntimeError("Failed to create refresh token") from exc


def decode_token(token: str, expected_type: str = "access") -> dict:
    try:
        payload = jwt.decode(
            token,
            settings.JWT_SECRET,
            algorithms=[settings.JWT_ALGORITHM],
        )
        token_type = payload.get("type")
        if token_type != expected_type:
            raise JWTError(
                f"Invalid token type: expected '{expected_type}', got '{token_type}'"
            )
        return payload
    except JWTError:
        raise
    except Exception as exc:
        logger.error(f"Unexpected token decode error: {exc}")
        raise JWTError(f"Token decode failed: {exc}") from exc
