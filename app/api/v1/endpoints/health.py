"""
Health Check Endpoint.
"""

import logging
from datetime import datetime, timezone

from fastapi import APIRouter, status
from fastapi.responses import JSONResponse
from sqlalchemy import text

from app.core.config import settings
from app.core.database import AsyncSessionFactory

logger = logging.getLogger(__name__)

router = APIRouter(tags=["Health"])


@router.get(
    "/health",
    summary="Service health check",
    status_code=status.HTTP_200_OK,
)
async def health_check():
    try:
        async with AsyncSessionFactory() as session:
            await session.execute(text("SELECT 1"))
        return {
            "status": "healthy",
            "service": settings.APP_NAME,
            "version": settings.APP_VERSION,
            "environment": settings.APP_ENV,
            "timestamp": datetime.now(timezone.utc).isoformat(),
        }
    except Exception as exc:
        logger.error(f"Health check failed — DB unreachable: {exc}")
        return JSONResponse(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            content={
                "status": "unhealthy",
                "service": settings.APP_NAME,
                "error": "Database connection failed",
                "timestamp": datetime.now(timezone.utc).isoformat(),
            },
        )
