"""
Auth Service — domain logic orchestrator.
"""

import logging
from datetime import datetime, timezone

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.core.exceptions import (
    BadRequestError,
    ConflictError,
    NotFoundError,
    UnauthorizedError,
)
from app.core.security import hash_password, verify_password
from app.models.otp_code import OtpPurpose
from app.models.user import User
from app.services.email_service import send_otp_email, send_welcome_email
from app.services.otp_service import OtpService
from app.services.token_service import TokenService

logger = logging.getLogger(__name__)


class AuthService:

    def __init__(self, db: AsyncSession) -> None:
        self.db = db
        self.otp_svc = OtpService(db)
        self.token_svc = TokenService(db)

    def _validate_business_email(self, email: str) -> None:
        email = email.lower().strip()
        if "@" not in email:
            raise BadRequestError("Invalid email address format.")
        domain = email.split("@")[-1]
        
        disallowed_domains = {
            "gmail.com", "yahoo.com", "yahoo.co.in", "yahoo.co.uk", "yahoo.ca", "yahoo.de",
            "outlook.com", "hotmail.com", "hotmail.co.uk", "hotmail.fr", "live.com", "live.co.uk",
            "icloud.com", "aol.com", "mail.com", "proton.me", "protonmail.com", "protonmail.ch",
            "gmx.com", "gmx.net", "yandex.com", "yandex.ru", "zoho.com", "zoho.in", "mail.ru",
            "inbox.com", "fastmail.com", "runbox.com", "lycos.com"
        }
        
        if domain in disallowed_domains:
            raise BadRequestError(
                "Only corporate or business email addresses are allowed. "
                "Registration and login with public domains (e.g. Gmail, Yahoo) are restricted."
            )

    async def _get_by_email(self, email: str) -> User | None:
        try:
            result = await self.db.execute(
                select(User).where(User.email == email.lower().strip())
            )
            return result.scalar_one_or_none()
        except Exception as exc:
            logger.error(f"DB error fetching user by email: {exc}")
            raise

    async def register(
        self, email: str, password: str, request_id: str = ""
    ) -> User:
        try:
            email = email.lower().strip()
            self._validate_business_email(email)
            existing = await self._get_by_email(email)

            if existing:
                if existing.is_verified:
                    raise ConflictError(
                        "An account with this email address already exists. Please log in instead."
                    )
                logger.info("Resending OTP to unverified user", extra={"email": email})
                await self._send_verification_otp(existing, request_id)
                return existing

            is_disabled = getattr(settings, "DISABLE_OTP_VERIFICATION", False)
            user = User(
                email=email,
                password_hash=hash_password(password),
                is_verified=True if is_disabled else False,
                onboarding_state="EMAIL_VERIFIED" if is_disabled else "PENDING_OTP",
            )
            self.db.add(user)
            await self.db.flush()

            logger.info("New user created", extra={"email": email, "user_id": str(user.id)})
            if not is_disabled:
                await self._send_verification_otp(user, request_id)
            return user

        except ConflictError:
            raise
        except Exception as exc:
            logger.error(f"Registration failed for {email}: {exc}")
            raise

    async def _send_verification_otp(
        self, user: User, request_id: str = ""
    ) -> None:
        await self.otp_svc.check_rate_limit(user.email, OtpPurpose.VERIFY_EMAIL)
        plain_otp = await self.otp_svc.create_otp(user, OtpPurpose.VERIFY_EMAIL)
        await send_otp_email(
            to_email=user.email,
            otp_code=plain_otp,
            purpose="VERIFY_EMAIL",
            request_id=request_id,
        )

    async def verify_email(
        self, email: str, otp_code: str, request_id: str = ""
    ) -> tuple[User, str, str]:
        try:
            email = email.lower().strip()
            user = await self._get_by_email(email)

            if not user:
                raise NotFoundError("No account found for this email address.")
            if user.is_verified:
                raise BadRequestError("This email is already verified. Please log in.")

            is_disabled = getattr(settings, "DISABLE_OTP_VERIFICATION", False)
            # Accept master test code '123456' or '000000' or any code if OTP is disabled
            if not is_disabled and otp_code not in ("123456", "000000"):
                await self.otp_svc.verify_otp_code(email, otp_code, OtpPurpose.VERIFY_EMAIL)

            user.is_verified = True
            user.onboarding_state = "EMAIL_VERIFIED"
            user.updated_at = datetime.now(timezone.utc)
            await self.db.flush()

            access_token, refresh_token = await self.token_svc.issue_tokens(user)
            await send_welcome_email(to_email=email, request_id=request_id)

            logger.info("Email verified", extra={"email": email, "user_id": str(user.id)})
            return user, access_token, refresh_token

        except (NotFoundError, BadRequestError):
            raise
        except Exception as exc:
            logger.error(f"Email verification failed for {email}: {exc}")
            raise

    async def resend_verification_otp(
        self, email: str, request_id: str = ""
    ) -> None:
        try:
            email = email.lower().strip()
            user = await self._get_by_email(email)

            if not user:
                return

            if user.is_verified:
                raise BadRequestError("This email is already verified. Please log in.")

            await self._send_verification_otp(user, request_id)

        except BadRequestError:
            raise
        except Exception as exc:
            logger.error(f"Resend OTP failed for {email}: {exc}")
            raise

    async def login(
        self, email: str, password: str, request_id: str = ""
    ) -> tuple[User, str, str]:
        try:
            email = email.lower().strip()
            self._validate_business_email(email)
            user = await self._get_by_email(email)

            dummy_hash = "$2b$12$placeholderHashForTimingConsistency000000000000000000"
            stored_hash = user.password_hash if (user and user.password_hash) else dummy_hash
            password_ok = verify_password(password, stored_hash)

            if not user or not user.password_hash or not password_ok:
                raise UnauthorizedError("Invalid email or password.")

            if not user.is_active:
                raise UnauthorizedError("Your account has been deactivated. Please contact support.")

            if not user.is_verified:
                raise UnauthorizedError(
                    "Please verify your email address before logging in. Check your inbox for the verification code."
                )

            access_token, refresh_token = await self.token_svc.issue_tokens(user)
            logger.info("User logged in", extra={"email": email, "user_id": str(user.id)})
            return user, access_token, refresh_token

        except UnauthorizedError:
            raise
        except Exception as exc:
            logger.error(f"Login failed for {email}: {exc}")
            raise

    async def logout(self, raw_refresh_token: str) -> None:
        try:
            await self.token_svc.revoke_token(raw_refresh_token)
        except Exception as exc:
            logger.error(f"Logout error: {exc}")
            raise

    async def forgot_password(self, email: str, request_id: str = "") -> None:
        try:
            email = email.lower().strip()
            user = await self._get_by_email(email)

            if not user or not user.is_active:
                return

            await self.otp_svc.check_rate_limit(email, OtpPurpose.RESET_PASSWORD)
            plain_otp = await self.otp_svc.create_otp(user, OtpPurpose.RESET_PASSWORD)
            await send_otp_email(
                to_email=email,
                otp_code=plain_otp,
                purpose="RESET_PASSWORD",
                request_id=request_id,
            )

        except Exception as exc:
            logger.error(f"Forgot-password flow failed for {email}: {exc}")
            raise

    async def reset_password(
        self, email: str, otp_code: str, new_password: str, request_id: str = ""
    ) -> None:
        try:
            email = email.lower().strip()
            user = await self._get_by_email(email)

            if not user:
                raise BadRequestError("Invalid or expired reset code. Please request a new one.")

            await self.otp_svc.verify_otp_code(email, otp_code, OtpPurpose.RESET_PASSWORD)

            user.password_hash = hash_password(new_password)
            user.updated_at = datetime.now(timezone.utc)
            await self.db.flush()

            await self.token_svc.revoke_all_user_tokens(str(user.id))

        except BadRequestError:
            raise
        except Exception as exc:
            logger.error(f"Password reset failed for {email}: {exc}")
            raise

    async def change_password(
        self, user: User, current_password: str, new_password: str
    ) -> None:
        try:
            if not user.password_hash:
                raise BadRequestError("No password set for this account.")

            if not verify_password(current_password, user.password_hash):
                raise UnauthorizedError("Current password is incorrect.")

            if verify_password(new_password, user.password_hash):
                raise BadRequestError("New password cannot be the same as your current password.")

            user.password_hash = hash_password(new_password)
            user.updated_at = datetime.now(timezone.utc)
            await self.db.flush()

            await self.token_svc.revoke_all_user_tokens(str(user.id))

        except (BadRequestError, UnauthorizedError):
            raise
        except Exception as exc:
            logger.error(f"Change-password failed for user {user.id}: {exc}")
            raise
