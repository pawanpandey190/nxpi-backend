"""
Auth API endpoints.
"""

import logging
from typing import Optional

from fastapi import APIRouter, Cookie, Depends, Request, Response, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.core.database import get_db
from app.core.dependencies import get_current_user, get_request_id
from app.core.exceptions import UnauthorizedError
from app.models.user import User
from app.schemas.auth import (
    AuthResponse,
    ChangePasswordRequest,
    ForgotPasswordRequest,
    LoginRequest,
    MessageResponse,
    OtpSendRequest,
    OtpVerifyRequest,
    RefreshTokenRequest,
    RegisterRequest,
    ResetPasswordRequest,
    TokenResponse,
    UserResponse,
)
from app.services.auth_service import AuthService
from app.services.token_service import TokenService

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/auth", tags=["Authentication"])

_COOKIE_NAME = "nxpi_refresh_token"
_COOKIE_PATH = "/api/v1/auth"
_COOKIE_MAX_AGE = settings.JWT_REFRESH_TOKEN_EXPIRE_DAYS * 86_400
_COOKIE_SECURE = settings.APP_ENV != "local"


def _set_refresh_cookie(response: Response, token: str) -> None:
    response.set_cookie(
        key=_COOKIE_NAME,
        value=token,
        httponly=True,
        samesite="strict",
        secure=_COOKIE_SECURE,
        max_age=_COOKIE_MAX_AGE,
        path=_COOKIE_PATH,
    )


def _clear_refresh_cookie(response: Response) -> None:
    response.delete_cookie(key=_COOKIE_NAME, path=_COOKIE_PATH)


@router.get(
    "/me",
    response_model=UserResponse,
    status_code=status.HTTP_200_OK,
    summary="Get current logged in user details",
)
async def get_me(
    current_user: User = Depends(get_current_user),
) -> UserResponse:
    return UserResponse.model_validate(current_user)


@router.post(
    "/register",
    response_model=MessageResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Register a new account",
)
async def register(
    body: RegisterRequest,
    request: Request,
    db: AsyncSession = Depends(get_db),
) -> MessageResponse:
    request_id = get_request_id(request)
    try:
        service = AuthService(db)
        await service.register(
            email=body.email,
            password=body.password,
            request_id=request_id,
        )
        return MessageResponse(
            message=(
                f"Account created. A {settings.OTP_EXPIRE_MINUTES}-minute verification "
                f"code has been sent to {body.email}. Please check your inbox."
            )
        )
    except Exception:
        raise


@router.post(
    "/otp/verify",
    response_model=AuthResponse,
    status_code=status.HTTP_200_OK,
    summary="Verify email with OTP",
)
async def verify_email(
    body: OtpVerifyRequest,
    request: Request,
    response: Response,
    db: AsyncSession = Depends(get_db),
) -> AuthResponse:
    request_id = get_request_id(request)
    try:
        service = AuthService(db)
        user, access_token, refresh_token = await service.verify_email(
            email=body.email,
            otp_code=body.otp_code,
            request_id=request_id,
        )
        _set_refresh_cookie(response, refresh_token)
        return AuthResponse(
            user=UserResponse.model_validate(user),
            access_token=access_token,
            token_type="bearer",
            expires_in=settings.JWT_ACCESS_TOKEN_EXPIRE_MINUTES * 60,
        )
    except Exception:
        raise


@router.post(
    "/otp/resend",
    response_model=MessageResponse,
    status_code=status.HTTP_200_OK,
    summary="Resend verification OTP",
)
async def resend_otp(
    body: OtpSendRequest,
    request: Request,
    db: AsyncSession = Depends(get_db),
) -> MessageResponse:
    request_id = get_request_id(request)
    try:
        service = AuthService(db)
        await service.resend_verification_otp(email=body.email, request_id=request_id)
        return MessageResponse(
            message=f"If an unverified account exists for {body.email}, a new code has been sent."
        )
    except Exception:
        raise


@router.post(
    "/login",
    response_model=AuthResponse,
    status_code=status.HTTP_200_OK,
    summary="Log in",
)
async def login(
    body: LoginRequest,
    request: Request,
    response: Response,
    db: AsyncSession = Depends(get_db),
) -> AuthResponse:
    request_id = get_request_id(request)
    try:
        service = AuthService(db)
        user, access_token, refresh_token = await service.login(
            email=body.email,
            password=body.password,
            request_id=request_id,
        )
        _set_refresh_cookie(response, refresh_token)
        return AuthResponse(
            user=UserResponse.model_validate(user),
            access_token=access_token,
            token_type="bearer",
            expires_in=settings.JWT_ACCESS_TOKEN_EXPIRE_MINUTES * 60,
        )
    except Exception:
        raise


@router.post(
    "/logout",
    response_model=MessageResponse,
    status_code=status.HTTP_200_OK,
    summary="Log out",
)
async def logout(
    response: Response,
    body: Optional[RefreshTokenRequest] = None,
    cookie_token: Optional[str] = Cookie(None, alias=_COOKIE_NAME),
    db: AsyncSession = Depends(get_db),
) -> MessageResponse:
    try:
        raw_token = (body.refresh_token if body else None) or cookie_token
        if raw_token:
            service = AuthService(db)
            await service.logout(raw_token)
        _clear_refresh_cookie(response)
        return MessageResponse(message="Logged out successfully.")
    except Exception as exc:
        logger.error(f"Logout error: {exc}")
        _clear_refresh_cookie(response)
        return MessageResponse(message="Logged out.")


@router.post(
    "/token/refresh",
    response_model=TokenResponse,
    status_code=status.HTTP_200_OK,
    summary="Refresh access token",
)
async def refresh_token(
    response: Response,
    body: Optional[RefreshTokenRequest] = None,
    cookie_token: Optional[str] = Cookie(None, alias=_COOKIE_NAME),
    db: AsyncSession = Depends(get_db),
) -> TokenResponse:
    try:
        raw_token = (body.refresh_token if body else None) or cookie_token
        if not raw_token:
            raise UnauthorizedError("No refresh token provided.")

        token_svc = TokenService(db)
        new_access, new_refresh = await token_svc.refresh_access_token(raw_token)

        _set_refresh_cookie(response, new_refresh)
        return TokenResponse(
            access_token=new_access,
            token_type="bearer",
            expires_in=settings.JWT_ACCESS_TOKEN_EXPIRE_MINUTES * 60,
        )
    except UnauthorizedError:
        _clear_refresh_cookie(response)
        raise
    except Exception as exc:
        logger.error(f"Token refresh endpoint error: {exc}")
        _clear_refresh_cookie(response)
        raise UnauthorizedError("Session expired. Please log in again.")


@router.post(
    "/forgot-password",
    response_model=MessageResponse,
    status_code=status.HTTP_200_OK,
    summary="Request password reset",
)
async def forgot_password(
    body: ForgotPasswordRequest,
    request: Request,
    db: AsyncSession = Depends(get_db),
) -> MessageResponse:
    request_id = get_request_id(request)
    try:
        service = AuthService(db)
        await service.forgot_password(email=body.email, request_id=request_id)
    except Exception as exc:
        logger.error(f"Forgot-password error: {exc}")

    return MessageResponse(
        message=f"If an account exists for {body.email}, a password reset code has been sent."
    )


@router.post(
    "/reset-password",
    response_model=MessageResponse,
    status_code=status.HTTP_200_OK,
    summary="Reset password with OTP",
)
async def reset_password(
    body: ResetPasswordRequest,
    request: Request,
    db: AsyncSession = Depends(get_db),
) -> MessageResponse:
    request_id = get_request_id(request)
    try:
        service = AuthService(db)
        await service.reset_password(
            email=body.email,
            otp_code=body.otp_code,
            new_password=body.new_password,
            request_id=request_id,
        )
        return MessageResponse(message="Password reset successfully. Please log in.")
    except Exception:
        raise


@router.post(
    "/change-password",
    response_model=MessageResponse,
    status_code=status.HTTP_200_OK,
    summary="Change password",
)
async def change_password(
    body: ChangePasswordRequest,
    response: Response,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> MessageResponse:
    try:
        service = AuthService(db)
        await service.change_password(
            user=current_user,
            current_password=body.current_password,
            new_password=body.new_password,
        )
        _clear_refresh_cookie(response)
        return MessageResponse(message="Password changed. You have been logged out of all devices.")
    except Exception:
        raise


@router.get(
    "/me",
    response_model=UserResponse,
    status_code=status.HTTP_200_OK,
    summary="Get current user profile",
)
async def get_me(current_user: User = Depends(get_current_user)) -> UserResponse:
    return UserResponse.model_validate(current_user)
