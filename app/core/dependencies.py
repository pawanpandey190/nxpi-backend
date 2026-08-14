"""
FastAPI dependency injection providers.
"""

import logging
from typing import Annotated

from fastapi import Depends, Request
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from jose import JWTError
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.core.exceptions import ForbiddenError, UnauthorizedError
from app.core.security import decode_token

logger = logging.getLogger(__name__)

_bearer = HTTPBearer(auto_error=False)


async def get_current_user_id(
    credentials: Annotated[HTTPAuthorizationCredentials | None, Depends(_bearer)],
) -> str:
    if not credentials:
        raise UnauthorizedError("No authentication token provided")

    try:
        payload = decode_token(credentials.credentials, expected_type="access")
    except JWTError as exc:
        logger.warning(f"JWT validation failed: {exc}")
        raise UnauthorizedError("Invalid or expired token. Please log in again.")
    except Exception as exc:
        logger.error(f"Unexpected error during token decoding: {exc}")
        raise UnauthorizedError("Authentication failed")

    user_id: str | None = payload.get("sub")
    if not user_id:
        raise UnauthorizedError("Token is missing required claims")

    return user_id


async def get_current_user(
    user_id: str = Depends(get_current_user_id),
    db: AsyncSession = Depends(get_db),
):
    from app.models.user import User

    try:
        result = await db.execute(select(User).where(User.id == user_id))
        user = result.scalar_one_or_none()
    except Exception as exc:
        logger.error(f"DB error fetching user (id={user_id}): {exc}")
        raise UnauthorizedError("Authentication check failed")

    if not user:
        raise UnauthorizedError("User account not found")
    if not user.is_active:
        raise UnauthorizedError("Your account has been deactivated. Contact support.")

    return user


async def require_admin(user=Depends(get_current_user)):
    if user.role not in ("ADMIN", "SUPER_ADMIN"):
        raise ForbiddenError("Admin access required")
    return user


def get_request_id(request: Request) -> str:
    return getattr(request.state, "request_id", "unknown")
