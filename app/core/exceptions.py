"""
Custom HTTP exception classes for NXPI Monolith.
"""

from fastapi import HTTPException, status


class AppServiceError(HTTPException):
    """Base class for all backend domain exceptions."""
    pass


class BadRequestError(AppServiceError):
    def __init__(self, detail: str = "Bad request") -> None:
        super().__init__(status_code=status.HTTP_400_BAD_REQUEST, detail=detail)


class UnauthorizedError(AppServiceError):
    def __init__(self, detail: str = "Authentication required") -> None:
        super().__init__(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail=detail,
            headers={"WWW-Authenticate": "Bearer"},
        )


class ForbiddenError(AppServiceError):
    def __init__(self, detail: str = "You do not have permission to perform this action") -> None:
        super().__init__(status_code=status.HTTP_403_FORBIDDEN, detail=detail)


class NotFoundError(AppServiceError):
    def __init__(self, detail: str = "Resource not found") -> None:
        super().__init__(status_code=status.HTTP_404_NOT_FOUND, detail=detail)


class ConflictError(AppServiceError):
    def __init__(self, detail: str = "A conflict occurred with the current state") -> None:
        super().__init__(status_code=status.HTTP_409_CONFLICT, detail=detail)


class RateLimitError(AppServiceError):
    def __init__(self, detail: str = "Too many requests. Please try again later.") -> None:
        super().__init__(status_code=status.HTTP_429_TOO_MANY_REQUESTS, detail=detail)
