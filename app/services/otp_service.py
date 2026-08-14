"""
OTP lifecycle service: rate limiting, hashing, storage, and verification.
"""

import logging
from datetime import datetime, timedelta, timezone

from sqlalchemy import and_, func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.core.exceptions import BadRequestError, RateLimitError
from app.core.security import generate_otp, hash_otp, verify_otp
from app.models.otp_code import OtpCode, OtpPurpose
from app.models.user import User

logger = logging.getLogger(__name__)


class OtpService:

    def __init__(self, db: AsyncSession) -> None:
        self.db = db

    async def check_rate_limit(self, email: str, purpose: OtpPurpose) -> None:
        try:
            window_start = datetime.now(timezone.utc) - timedelta(
                minutes=settings.OTP_RATE_LIMIT_WINDOW_MINUTES
            )
            result = await self.db.execute(
                select(func.count(OtpCode.id)).where(
                    and_(
                        OtpCode.email == email,
                        OtpCode.purpose == purpose,
                        OtpCode.created_at >= window_start,
                    )
                )
            )
            count = result.scalar_one()

            if count >= settings.OTP_RATE_LIMIT_MAX:
                logger.warning("OTP rate limit hit", extra={"email": email, "purpose": purpose})
                raise RateLimitError(
                    f"Too many verification codes requested. "
                    f"Please wait {settings.OTP_RATE_LIMIT_WINDOW_MINUTES} minutes before trying again."
                )
        except RateLimitError:
            raise
        except Exception as exc:
            logger.error(f"Rate-limit check DB error for {email}: {exc}")
            raise

    async def create_otp(self, user: User, purpose: OtpPurpose) -> str:
        try:
            await self._invalidate_prior_otps(user.id, purpose)

            plain_otp = generate_otp()
            expires_at = datetime.now(timezone.utc) + timedelta(
                minutes=settings.OTP_EXPIRE_MINUTES
            )

            otp_record = OtpCode(
                user_id=user.id,
                email=user.email,
                code_hash=hash_otp(plain_otp),
                purpose=purpose,
                expires_at=expires_at,
            )
            self.db.add(otp_record)
            await self.db.flush()

            logger.info("OTP created", extra={"email": user.email, "purpose": purpose})
            return plain_otp
        except Exception as exc:
            logger.error(f"OTP creation failed for {user.email}: {exc}")
            raise

    async def _invalidate_prior_otps(self, user_id, purpose: OtpPurpose) -> None:
        try:
            result = await self.db.execute(
                select(OtpCode).where(
                    and_(
                        OtpCode.user_id == user_id,
                        OtpCode.purpose == purpose,
                        OtpCode.used_at.is_(None),
                    )
                )
            )
            prior = result.scalars().all()
            now = datetime.now(timezone.utc)
            for otp in prior:
                otp.used_at = now
        except Exception as exc:
            logger.error(f"Failed to invalidate prior OTPs: {exc}")
            raise

    async def verify_otp_code(
        self, email: str, plain_otp: str, purpose: OtpPurpose
    ) -> OtpCode:
        try:
            otp_record = await self._get_latest_valid_otp(email, purpose)

            if otp_record is None:
                raise BadRequestError(
                    "Invalid or expired verification code. Please request a new one."
                )

            otp_record.attempts += 1
            await self.db.flush()

            if otp_record.is_max_attempts_reached:
                raise BadRequestError(
                    "Too many incorrect attempts. Please request a new verification code."
                )

            if not verify_otp(plain_otp, otp_record.code_hash):
                remaining = otp_record.attempts_remaining
                if remaining == 0:
                    raise BadRequestError(
                        "Too many incorrect attempts. Please request a new verification code."
                    )
                raise BadRequestError(f"Incorrect code. {remaining} attempt(s) remaining.")

            otp_record.used_at = datetime.now(timezone.utc)
            await self.db.flush()
            return otp_record

        except BadRequestError:
            raise
        except Exception as exc:
            logger.error(f"OTP verification error for {email}: {exc}")
            raise

    async def _get_latest_valid_otp(
        self, email: str, purpose: OtpPurpose
    ) -> OtpCode | None:
        try:
            result = await self.db.execute(
                select(OtpCode)
                .where(
                    and_(
                        OtpCode.email == email,
                        OtpCode.purpose == purpose,
                        OtpCode.used_at.is_(None),
                        OtpCode.expires_at > datetime.now(timezone.utc),
                    )
                )
                .order_by(OtpCode.created_at.desc())
                .limit(1)
            )
            return result.scalar_one_or_none()
        except Exception as exc:
            logger.error(f"DB error fetching OTP for {email}: {exc}")
            raise
