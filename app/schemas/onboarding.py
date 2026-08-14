"""
Onboarding Pydantic Schemas.
"""

import uuid
from datetime import datetime
from typing import Optional

from pydantic import BaseModel, Field


class CountryDocumentRuleResponse(BaseModel):
    id: uuid.UUID
    country_code: str
    country_name: str
    company_registration_label: str
    tax_identity_label: str
    indirect_tax_label: str

    model_config = {"from_attributes": True}


class CompanyInfoRequest(BaseModel):
    name: str = Field(min_length=2, max_length=255)
    industry: Optional[str] = Field(None, max_length=100)
    team_size: Optional[str] = Field(None, max_length=50)


class ClientOnboardingRequest(BaseModel):
    country: str = Field(min_length=2, max_length=100)
    company_name: str = Field(min_length=2, max_length=255)
    company_website: Optional[str] = Field(None, max_length=255)
    team_size: Optional[str] = Field(None, max_length=50)
    phone_number: Optional[str] = Field(None, max_length=50)
    address: Optional[str] = None
    doc_category: str = Field(description="COMPANY_REGISTRATION, TAX_IDENTITY, or INDIRECT_TAX")
    doc_name: str = Field(description="Exact document label (e.g. PAN, CIN, GSTIN, EIN)")
    doc_number: str = Field(min_length=1, max_length=255)


class OrganizationResponse(BaseModel):
    id: uuid.UUID
    name: str
    domain: Optional[str] = None
    industry: Optional[str] = None
    team_size: Optional[str] = None
    country: Optional[str] = None
    address: Optional[str] = None
    phone_number: Optional[str] = None
    selected_doc_category: Optional[str] = None
    document_name: Optional[str] = None
    document_number: Optional[str] = None
    document_file_url: Optional[str] = None
    discussion_date: Optional[str] = None
    discussion_time: Optional[str] = None
    discussion_timezone: Optional[str] = None
    meet_link: Optional[str] = None
    use_case: Optional[str] = None
    status: str
    owner_user_id: uuid.UUID
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}


class OnboardingStatusResponse(BaseModel):
    user_id: uuid.UUID
    email: str
    onboarding_state: str
    organization: Optional[OrganizationResponse] = None


class OnboardingResumeResponse(BaseModel):
    state: str
    redirect_url: str
