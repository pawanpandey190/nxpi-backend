"""
Admin Pydantic Schemas.
"""

import uuid
from datetime import datetime
from typing import Any, Dict, Generic, List, Optional, TypeVar

from pydantic import BaseModel, Field

T = TypeVar("T")


class PaginatedResponse(BaseModel, Generic[T]):
    items: List[T]
    total: int
    page: int
    size: int
    pages: int


class AdminUserResponse(BaseModel):
    id: uuid.UUID
    email: str
    role: str
    is_verified: bool
    is_active: bool
    onboarding_state: str
    created_at: datetime

    model_config = {"from_attributes": True}


class AdminOrgResponse(BaseModel):
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
    status: str
    owner_user_id: uuid.UUID
    owner_email: Optional[str] = None
    edit_count: int = 0
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}


class AdminUpdateStatusRequest(BaseModel):
    status: str = Field(description="PENDING_REVIEW, VERIFIED, REJECTED, or ACTIVE")


class AdminOrgEventResponse(BaseModel):
    id: uuid.UUID
    org_id: uuid.UUID
    from_state: str
    to_state: str
    triggered_by: str
    metadata_json: Optional[Dict[str, Any]] = None
    created_at: datetime

    model_config = {"from_attributes": True}


class FunnelStageMetric(BaseModel):
    stage: str
    count: int
    percentage: float
