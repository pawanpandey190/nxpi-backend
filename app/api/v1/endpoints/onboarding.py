"""
Onboarding API endpoints.
"""

import logging
import os
import uuid
from pathlib import Path
from typing import List, Optional

from fastapi import APIRouter, Depends, File, Form, UploadFile, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.core.dependencies import get_current_user
from app.models.user import User
from app.schemas.onboarding import (
    CompanyInfoRequest,
    CountryDocumentRuleResponse,
    OnboardingResumeResponse,
    OnboardingStatusResponse,
    OrganizationResponse,
)
from app.services.onboarding_service import OnboardingService

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/onboarding", tags=["Onboarding"])

UPLOADS_DIR = Path(__file__).parent.parent.parent.parent / "uploads"
UPLOADS_DIR.mkdir(parents=True, exist_ok=True)


@router.get(
    "/country-rules",
    response_model=List[CountryDocumentRuleResponse],
    status_code=status.HTTP_200_OK,
    summary="Get all country document compliance rules",
)
async def get_country_rules(
    db: AsyncSession = Depends(get_db),
) -> List[CountryDocumentRuleResponse]:
    try:
        service = OnboardingService(db)
        rules = await service.get_all_country_rules()
        return [CountryDocumentRuleResponse.model_validate(r) for r in rules]
    except Exception:
        raise


@router.get(
    "/status",
    response_model=OnboardingStatusResponse,
    status_code=status.HTTP_200_OK,
    summary="Get user onboarding status",
)
async def get_status(
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> OnboardingStatusResponse:
    try:
        service = OnboardingService(db)
        org = await service.get_user_organization(str(current_user.id))
        org_resp = OrganizationResponse.model_validate(org) if org else None

        return OnboardingStatusResponse(
            user_id=current_user.id,
            email=current_user.email,
            onboarding_state=current_user.onboarding_state,
            organization=org_resp,
        )
    except Exception:
        raise


@router.post(
    "/submit-details",
    response_model=OrganizationResponse,
    status_code=status.HTTP_200_OK,
    summary="Submit client onboarding company details and compliance documents",
)
async def submit_onboarding_details(
    country: str = Form(...),
    company_name: str = Form(...),
    company_website: Optional[str] = Form(None),
    team_size: Optional[str] = Form(None),
    phone_number: Optional[str] = Form(None),
    address: Optional[str] = Form(None),
    doc_category: Optional[str] = Form(None),
    doc_name: Optional[str] = Form(None),
    doc_number: Optional[str] = Form(None),
    discussion_date: Optional[str] = Form(None),
    discussion_time: Optional[str] = Form(None),
    discussion_timezone: Optional[str] = Form(None),
    use_case: Optional[str] = Form(None),
    document_file: Optional[UploadFile] = File(None),
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> OrganizationResponse:
    try:
        file_url = None
        if document_file and document_file.filename:
            file_ext = os.path.splitext(document_file.filename)[1]
            unique_filename = f"{uuid.uuid4().hex}{file_ext}"
            file_path = UPLOADS_DIR / unique_filename
            content = await document_file.read()
            with open(file_path, "wb") as f:
                f.write(content)
            file_url = f"/uploads/{unique_filename}"

        service = OnboardingService(db)
        org = await service.save_client_onboarding(
            user=current_user,
            country=country,
            company_name=company_name,
            company_website=company_website,
            team_size=team_size,
            phone_number=phone_number,
            address=address,
            doc_category=doc_category,
            doc_name=doc_name,
            doc_number=doc_number,
            doc_file_url=file_url,
            discussion_date=discussion_date,
            discussion_time=discussion_time,
            discussion_timezone=discussion_timezone,
            use_case=use_case,
        )
        return OrganizationResponse.model_validate(org)
    except Exception:
        raise


@router.get(
    "/resume",
    response_model=OnboardingResumeResponse,
    status_code=status.HTTP_200_OK,
    summary="Get redirect URL based on current onboarding state",
)
async def resume_onboarding(
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> OnboardingResumeResponse:
    try:
        service = OnboardingService(db)
        result = await service.get_resume_route(current_user)
        return OnboardingResumeResponse(**result)
    except Exception:
        raise
