"""
Token service: access & refresh token rotation and revocation.
"""

import hashlib
import logging
from datetime import datetime, timezone

from jose import JWTError
from sqlalchemy import and_, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.core.exceptions import UnauthorizedError
from app.core.security import create_access_token, create_refresh_token, decode_token
from app.models.refresh_token import RefreshToken

logger = logging.getLogger(__name__)


def _sha256(raw_token: str) -> str:
    return hashlib.sha256(raw_token.encode()).hexdigest()


class TokenService:

    def __init__(self, db: AsyncSession) -> None:
        self.db = db

    def _build_payload(self, user) -> dict:
        return {
            "sub": str(user.id),
            "email": user.email,
            "role": user.role,
            "onboarding_state": user.onboarding_state,
        }

    async def issue_tokens(self, user) -> tuple[str, str]:
        try:
            payload = self._build_payload(user)
            access_token = create_access_token(payload)
            raw_refresh, expire_at = create_refresh_token(payload)

            record = RefreshToken(
                user_id=user.id,
                token_hash=_sha256(raw_refresh),
                expires_at=expire_at,
            )
            self.db.add(record)
            await self.db.flush()
            return access_token, raw_refresh
        except Exception as exc:
            logger.error(f"Token issuance failed for user {user.id}: {exc}")
            raise

    async def refresh_access_token(self, raw_refresh: str) -> tuple[str, str]:
        try:
            try:
                payload = decode_token(raw_refresh, expected_type="refresh")
            except JWTError as exc:
                raise UnauthorizedError("Invalid or expired session. Please log in again.")

            user_id = payload.get("sub")
            if not user_id:
                raise UnauthorizedError("Malformed refresh token")

            token_hash = _sha256(raw_refresh)
            result = await self.db.execute(
                select(RefreshToken).where(
                    and_(
                        RefreshToken.token_hash == token_hash,
                        RefreshToken.revoked_at.is_(None),
                    )
                )
            )
            record = result.scalar_one_or_none()

            if not record or not record.is_valid:
                raise UnauthorizedError("Session expired or invalid. Please log in again.")

            from app.models.user import User
            user_result = await self.db.execute(
                select(User).where(User.id == user_id)
            )
            user = user_result.scalar_one_or_none()
            if not user or not user.is_active:
                raise UnauthorizedError("User account not found or deactivated.")

            record.revoked_at = datetime.now(timezone.utc)
            await self.db.flush()

            return await self.issue_tokens(user)
        except UnauthorizedError:
            raise
        except Exception as exc:
            logger.error(f"Token refresh failed: {exc}")
            raise

    async def revoke_token(self, raw_refresh: str) -> bool:
        try:
            token_hash = _sha256(raw_refresh)
            result = await self.db.execute(
                select(RefreshToken).where(
                    and_(
                        RefreshToken.token_hash == token_hash,
                        RefreshToken.revoked_at.is_(None),
                    )
                )
            )
            record = result.scalar_one_or_none()
            if not record:
                return False

            record.revoked_at = datetime.now(timezone.utc)
            await self.db.flush()
            return True
        except Exception as exc:
            logger.error(f"Token revocation failed: {exc}")
            raise

    async def revoke_all_user_tokens(self, user_id: str) -> int:
        try:
            result = await self.db.execute(
                select(RefreshToken).where(
                    and_(
                        RefreshToken.user_id == user_id,
                        RefreshToken.revoked_at.is_(None),
                    )
                )
            )
            tokens = result.scalars().all()
            now = datetime.now(timezone.utc)
            for t in tokens:
                t.revoked_at = now

            await self.db.flush()
            return len(tokens)
        except Exception as exc:
            logger.error(f"Bulk token revocation failed for {user_id}: {exc}")
            raise
