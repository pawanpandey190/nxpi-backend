"""
NXPI Monolith Backend — FastAPI application entry point.
"""

import logging
import uuid

from contextlib import asynccontextmanager
from pathlib import Path
from fastapi import FastAPI, Request, status
from fastapi.exceptions import RequestValidationError
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from fastapi.staticfiles import StaticFiles

from app.core.config import settings
from app.core.database import close_db
from app.core.exceptions import AppServiceError
from app.core.logging import configure_logging

configure_logging()
logger = logging.getLogger(__name__)

if settings.SENTRY_DSN:
    try:
        import sentry_sdk
        from sentry_sdk.integrations.fastapi import FastApiIntegration

        sentry_sdk.init(
            dsn=settings.SENTRY_DSN,
            integrations=[FastApiIntegration(transaction_style="endpoint")],
            environment=settings.APP_ENV,
            release=f"{settings.APP_NAME}@{settings.APP_VERSION}",
        )
        logger.info("Sentry initialised", extra={"env": settings.APP_ENV})
    except Exception as exc:
        logger.error(f"Sentry initialisation failed: {exc}")


async def seed_constant_admin_account() -> None:
    """Auto-seed constant admin user if not present in DB."""
    try:
        from app.core.database import AsyncSessionFactory
        from app.core.security import hash_password
        from app.models.user import User
        from sqlalchemy import select

        async with AsyncSessionFactory() as session:
            result = await session.execute(select(User).where(User.email == settings.ADMIN_EMAIL))
            admin_user = result.scalar_one_or_none()

            if not admin_user:
                admin_user = User(
                    email=settings.ADMIN_EMAIL,
                    password_hash=hash_password(settings.ADMIN_PASSWORD),
                    is_verified=True,
                    is_active=True,
                    role="ADMIN",
                    onboarding_state="ACTIVE",
                )
                session.add(admin_user)
                await session.commit()
                logger.info(f"Constant Admin account seeded successfully ({settings.ADMIN_EMAIL})")
            else:
                # Enforce admin credentials and verification
                admin_user.password_hash = hash_password(settings.ADMIN_PASSWORD)
                admin_user.role = "ADMIN"
                admin_user.is_verified = True
                admin_user.is_active = True
                admin_user.onboarding_state = "ACTIVE"
                await session.commit()
                logger.info(f"Admin account credentials and privileges enforced for {settings.ADMIN_EMAIL}")
    except Exception as exc:
        logger.error(f"Failed to seed admin account: {exc}")


async def seed_country_rules() -> None:
    """Auto-seed default 28 country document rules if empty."""
    try:
        from app.core.database import AsyncSessionFactory
        from app.models.country_document_rule import CountryDocumentRule
        from sqlalchemy import select

        country_rules_data = [
            ("IN", "India", "CIN / LLPIN / Registration No.", "PAN", "GSTIN"),
            ("US", "USA", "State Registration No.", "EIN", "State Sales Tax ID"),
            ("GB", "UK", "CRN", "UTR", "VAT"),
            ("CA", "Canada", "BN / Provincial No.", "BN / CRA ID", "GST/HST"),
            ("AU", "Australia", "ACN / ABN", "Tax ID / ABN", "GST"),
            ("SG", "Singapore", "UEN", "Tax ID", "GST"),
            ("AE", "UAE", "Trade Licence / CR", "Tax ID / Corporate Tax", "VAT TRN"),
            ("DE", "Germany", "Handelsregister No.", "Steuernummer / W-IdNr.", "VAT ID"),
            ("FR", "France", "SIREN / SIRET", "Tax ID", "VAT ID"),
            ("IT", "Italy", "Registro Imprese / REA", "Codice Fiscale", "Partita IVA"),
            ("ES", "Spain", "Registro Mercantil", "NIF", "VAT"),
            ("NL", "Netherlands", "KvK No.", "Tax ID", "VAT"),
            ("CH", "Switzerland", "UID/CHE", "Tax ID", "VAT"),
            ("JP", "Japan", "Corporate Number", "Tax ID", "Consumption Tax"),
            ("CN", "China", "USCC", "Tax ID", "VAT"),
            ("HK", "Hong Kong", "Company No.", "BRN / Tax ID", "No general VAT/GST"),
            ("KR", "South Korea", "Corporate No.", "Business Registration No.", "VAT"),
            ("MY", "Malaysia", "SSM Registration No.", "TIN", "SST"),
            ("ID", "Indonesia", "NIB", "NPWP", "VAT/PKP"),
            ("TH", "Thailand", "Company Registration No.", "Tax ID", "VAT"),
            ("VN", "Vietnam", "Enterprise Registration No.", "Tax ID", "VAT"),
            ("PH", "Philippines", "SEC Registration No.", "TIN", "VAT"),
            ("NZ", "New Zealand", "NZBN / Company No.", "IRD No.", "GST"),
            ("ZA", "South Africa", "CIPC No.", "Tax Reference No.", "VAT"),
            ("BR", "Brazil", "CNPJ", "CNPJ / Tax ID", "ICMS / ISS"),
            ("MX", "Mexico", "Company Registration", "RFC", "IVA/VAT"),
            ("SA", "Saudi Arabia", "Commercial Registration No.", "Tax ID", "VAT"),
            ("IE", "Ireland", "CRO No.", "Tax Reference No.", "VAT"),
        ]

        async with AsyncSessionFactory() as session:
            result = await session.execute(select(CountryDocumentRule))
            existing = result.scalars().all()
            if not existing:
                for code, name, comp, tax, ind_tax in country_rules_data:
                    rule = CountryDocumentRule(
                        country_code=code,
                        country_name=name,
                        company_registration_label=comp,
                        tax_identity_label=tax,
                        indirect_tax_label=ind_tax
                    )
                    session.add(rule)
                await session.commit()
                logger.info("Default country document rules seeded successfully")
            else:
                logger.info("Country document rules already initialized")
    except Exception as exc:
        logger.error(f"Failed to seed country document rules: {exc}")


@asynccontextmanager
async def lifespan(app: FastAPI):
    logger.info(
        "Monolith backend starting up",
        extra={"version": settings.APP_VERSION, "env": settings.APP_ENV},
    )
    await seed_constant_admin_account()
    await seed_country_rules()
    yield
    logger.info("Monolith backend shutting down")
    await close_db()


app = FastAPI(
    title="NXPI Backend API",
    description="Unified Monolith API for Negentrophi Customer Onboarding Platform.",
    version=settings.APP_VERSION,
    docs_url="/docs" if settings.APP_ENV != "production" else None,
    redoc_url="/redoc" if settings.APP_ENV != "production" else None,
    openapi_url="/openapi.json" if settings.APP_ENV != "production" else None,
    lifespan=lifespan,
)

_ALLOWED_ORIGINS = [
    "http://localhost:3000",
    "http://localhost:5173",
    "https://negentrophi.com",
    "https://www.negentrophi.com",
]

app.add_middleware(
    CORSMiddleware,
    allow_origins=_ALLOWED_ORIGINS,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
    expose_headers=["X-Request-ID"],
)


@app.middleware("http")
async def correlation_id_middleware(request: Request, call_next):
    request_id = request.headers.get("X-Request-ID") or str(uuid.uuid4())
    request.state.request_id = request_id
    try:
        response = await call_next(request)
        response.headers["X-Request-ID"] = request_id
        return response
    except Exception as exc:
        logger.error(
            f"Unhandled exception in middleware: {exc}",
            extra={"request_id": request_id, "path": str(request.url)},
        )
        raise


@app.exception_handler(AppServiceError)
async def app_service_error_handler(request: Request, exc: AppServiceError):
    return JSONResponse(
        status_code=exc.status_code,
        content={
            "success": False,
            "detail": exc.detail,
            "request_id": getattr(request.state, "request_id", None),
        },
        headers={"X-Request-ID": getattr(request.state, "request_id", "")},
    )


@app.exception_handler(RequestValidationError)
async def validation_error_handler(request: Request, exc: RequestValidationError):
    errors = []
    for error in exc.errors():
        loc = error.get("loc", [])
        field = " → ".join(str(l) for l in loc if l != "body")
        errors.append({"field": field or "unknown", "message": error["msg"]})

    return JSONResponse(
        status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
        content={
            "success": False,
            "detail": "Request validation failed",
            "errors": errors,
            "request_id": getattr(request.state, "request_id", None),
        },
    )


@app.exception_handler(Exception)
async def generic_exception_handler(request: Request, exc: Exception):
    request_id = getattr(request.state, "request_id", "unknown")
    logger.exception(
        "Unhandled exception",
        extra={"request_id": request_id, "path": str(request.url), "method": request.method},
    )
    return JSONResponse(
        status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
        content={
            "success": False,
            "detail": "An unexpected error occurred. Please try again or contact support.",
            "request_id": request_id,
        },
    )


# Mount uploads directory safely (if directory exists or can be created)
try:
    uploads_dir = Path(__file__).parent / "uploads"
    uploads_dir.mkdir(parents=True, exist_ok=True)
    app.mount("/uploads", StaticFiles(directory=uploads_dir), name="uploads")
except Exception as exc:
        logger.warning(f"Could not mount static uploads directory: {exc}")

from app.api.v1.router import api_router

app.include_router(api_router, prefix="/api/v1")
