"""
API v1 Router.
"""

from fastapi import APIRouter

from app.api.v1.endpoints.admin import router as admin_router
from app.api.v1.endpoints.auth import router as auth_router
from app.api.v1.endpoints.health import router as health_router
from app.api.v1.endpoints.onboarding import router as onboarding_router
from app.api.v1.endpoints.contact import router as contact_router

api_router = APIRouter()

api_router.include_router(health_router)
api_router.include_router(auth_router)
api_router.include_router(onboarding_router)
api_router.include_router(contact_router)
api_router.include_router(admin_router)
