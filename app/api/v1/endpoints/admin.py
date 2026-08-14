"""
Admin API endpoints.
"""

import math
from typing import List, Optional
import uuid

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.core.dependencies import get_current_user, require_admin
from app.models.onboarding_event import OnboardingEvent
from app.models.organization import Organization
from app.models.user import User
from app.schemas.admin import (
    AdminOrgEventResponse,
    AdminOrgResponse,
    AdminUpdateStatusRequest,
    AdminUserResponse,
    FunnelStageMetric,
    PaginatedResponse,
)

router = APIRouter(prefix="/admin", tags=["Admin"], dependencies=[Depends(require_admin)])


@router.get(
    "/users",
    response_model=PaginatedResponse[AdminUserResponse],
    status_code=status.HTTP_200_OK,
    summary="Get paginated users list",
)
async def list_users(
    page: int = Query(1, ge=1),
    size: int = Query(20, ge=1, le=100),
    db: AsyncSession = Depends(get_db),
):
    offset = (page - 1) * size
    total_query = await db.execute(select(func.count(User.id)))
    total = total_query.scalar_one()

    result = await db.execute(
        select(User).order_by(User.created_at.desc()).offset(offset).limit(size)
    )
    users = result.scalars().all()
    items = [AdminUserResponse.model_validate(u) for u in users]

    return PaginatedResponse(
        items=items,
        total=total,
        page=page,
        size=size,
        pages=math.ceil(total / size) if total > 0 else 0,
    )


@router.get(
    "/companies",
    response_model=PaginatedResponse[AdminOrgResponse],
    status_code=status.HTTP_200_OK,
    summary="Get registered companies list with owner email and edit count",
)
async def list_companies(
    page: int = Query(1, ge=1),
    size: int = Query(20, ge=1, le=100),
    search: Optional[str] = Query(None),
    status_filter: Optional[str] = Query(None),
    db: AsyncSession = Depends(get_db),
):
    offset = (page - 1) * size
    query = select(Organization, User.email).join(User, Organization.owner_user_id == User.id)

    if search:
        query = query.where(
            Organization.name.ilike(f"%{search}%") | User.email.ilike(f"%{search}%")
        )
    if status_filter:
        query = query.where(Organization.status == status_filter)

    total_query = await db.execute(select(func.count()).select_from(query.subquery()))
    total = total_query.scalar_one() or 0

    query = query.order_by(Organization.created_at.desc()).offset(offset).limit(size)
    result = await db.execute(query)
    rows = result.all()

    items = []
    for org, owner_email in rows:
        # Count total onboarding events (edits) for this org
        event_count_res = await db.execute(
            select(func.count(OnboardingEvent.id)).where(OnboardingEvent.org_id == org.id)
        )
        edit_count = event_count_res.scalar_one() or 0

        org_dict = AdminOrgResponse.model_validate(org).model_dump()
        org_dict["owner_email"] = owner_email
        org_dict["edit_count"] = edit_count
        items.append(AdminOrgResponse(**org_dict))

    return PaginatedResponse(
        items=items,
        total=total,
        page=page,
        size=size,
        pages=math.ceil(total / size) if total > 0 else 0,
    )


@router.get(
    "/companies/{org_id}/events",
    response_model=List[AdminOrgEventResponse],
    status_code=status.HTTP_200_OK,
    summary="Get organization audit trail history",
)
async def get_company_events(
    org_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
):
    result = await db.execute(
        select(OnboardingEvent)
        .where(OnboardingEvent.org_id == org_id)
        .order_by(OnboardingEvent.created_at.desc())
    )
    events = result.scalars().all()
    return [AdminOrgEventResponse.model_validate(e) for e in events]


@router.patch(
    "/companies/{org_id}/status",
    response_model=AdminOrgResponse,
    status_code=status.HTTP_200_OK,
    summary="Admin updates company onboarding status",
)
async def update_company_status(
    org_id: uuid.UUID,
    body: AdminUpdateStatusRequest,
    current_admin: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    result = await db.execute(select(Organization).where(Organization.id == org_id))
    org = result.scalar_one_or_none()
    if not org:
        raise HTTPException(status_code=404, detail="Organization not found")

    old_status = org.status
    org.status = body.status
    
    # Record admin status change event
    event = OnboardingEvent(
        org_id=org.id,
        from_state=old_status,
        to_state=body.status,
        triggered_by=f"ADMIN:{current_admin.email}",
        metadata_json={"new_status": body.status, "updated_by": current_admin.email},
    )
    db.add(event)
    await db.commit()
    await db.refresh(org)

    owner_res = await db.execute(select(User).where(User.id == org.owner_user_id))
    owner = owner_res.scalar_one_or_none()

    # Trigger Client Credentials & Verification Email if status is VERIFIED or ACTIVE
    if body.status in ["VERIFIED", "ACTIVE"] and owner:
        owner.onboarding_state = "ACTIVE"
        await db.commit()
        from app.services.email_service import send_client_verification_credentials_email
        await send_client_verification_credentials_email(
            client_email=owner.email,
            company_name=org.name,
            status_name=body.status,
        )

    event_count_res = await db.execute(
        select(func.count(OnboardingEvent.id)).where(OnboardingEvent.org_id == org.id)
    )
    edit_count = event_count_res.scalar_one() or 0

    org_dict = AdminOrgResponse.model_validate(org).model_dump()
    org_dict["owner_email"] = owner.email if owner else ""
    org_dict["edit_count"] = edit_count
    return AdminOrgResponse(**org_dict)


@router.get(
    "/onboarding-funnel",
    response_model=List[FunnelStageMetric],
    status_code=status.HTTP_200_OK,
    summary="Get onboarding funnel drop-off metrics",
)
async def get_funnel_metrics(db: AsyncSession = Depends(get_db)):
    result = await db.execute(
        select(User.onboarding_state, func.count(User.id)).group_by(User.onboarding_state)
    )
    counts = dict(result.all())
    total_users = sum(counts.values()) or 1

    stages = ["PENDING_OTP", "EMAIL_VERIFIED", "PROFILE_INCOMPLETE", "PENDING_PAYMENT", "ACTIVE"]
    metrics = []
    for stage in stages:
        cnt = counts.get(stage, 0)
        metrics.append(
            FunnelStageMetric(
                stage=stage,
                count=cnt,
                percentage=round((cnt / total_users) * 100, 2),
            )
        )
    return metrics
