"""
Onboarding Service — tracks organization profiles, country document rules, and onboarding state.
"""

import logging
from datetime import datetime, timezone

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.exceptions import BadRequestError, NotFoundError
from app.models.country_document_rule import CountryDocumentRule
from app.models.onboarding_event import OnboardingEvent
from app.models.organization import Organization
from app.models.user import User

logger = logging.getLogger(__name__)


class OnboardingService:

    def __init__(self, db: AsyncSession) -> None:
        self.db = db

    async def get_all_country_rules(self) -> list[CountryDocumentRule]:
        try:
            result = await self.db.execute(
                select(CountryDocumentRule).order_by(CountryDocumentRule.country_name.asc())
            )
            return list(result.scalars().all())
        except Exception as exc:
            logger.error(f"Failed to fetch country document rules: {exc}")
            raise

    async def get_user_organization(self, user_id: str) -> Organization | None:
        try:
            result = await self.db.execute(
                select(Organization).where(Organization.owner_user_id == user_id)
            )
            return result.scalar_one_or_none()
        except Exception as exc:
            logger.error(f"Failed to fetch organization for user {user_id}: {exc}")
            raise

    async def save_client_onboarding(
        self,
        user: User,
        country: str,
        company_name: str,
        company_website: str | None = None,
        team_size: str | None = None,
        phone_number: str | None = None,
        address: str | None = None,
        doc_category: str | None = None,
        doc_name: str | None = None,
        doc_number: str | None = None,
        doc_file_url: str | None = None,
        discussion_date: str | None = None,
        discussion_time: str | None = None,
        discussion_timezone: str | None = None,
        use_case: str | None = None,
    ) -> Organization:
        try:
            org = await self.get_user_organization(str(user.id))
            fallback_domain = user.email.split("@")[-1] if "@" in user.email else None
            domain = company_website.strip() if company_website else fallback_domain
            from_state = user.onboarding_state

            if discussion_date and discussion_time:
                from sqlalchemy import select
                query = select(Organization).where(
                    Organization.discussion_date == discussion_date,
                    Organization.discussion_time == discussion_time
                )
                if org is not None:
                    query = query.where(Organization.id != org.id)
                res = await self.db.execute(query)
                conflicting_org = res.scalars().first()
                if conflicting_org:
                    from fastapi import HTTPException
                    raise HTTPException(
                        status_code=400,
                        detail="The selected time slot is already booked. Please choose a different date or time."
                    )

            # Generate Google Meet link & event if discussion schedule provided
            meet_link = None
            if discussion_date and discussion_time:
                from app.services.google_calendar_service import create_google_meet_event
                meet_link, _ = await create_google_meet_event(
                    company_name=company_name,
                    client_email=user.email,
                    discussion_date=discussion_date,
                    discussion_time=discussion_time,
                    discussion_timezone=discussion_timezone or "Asia/Kolkata",
                )

            if org is None:
                org = Organization(
                    name=company_name,
                    domain=domain,
                    country=country,
                    team_size=team_size,
                    phone_number=phone_number,
                    address=address,
                    selected_doc_category=doc_category,
                    document_name=doc_name,
                    document_number=doc_number,
                    document_file_url=doc_file_url,
                    discussion_date=discussion_date,
                    discussion_time=discussion_time,
                    discussion_timezone=discussion_timezone,
                    meet_link=meet_link,
                    use_case=use_case,
                    status="PENDING_REVIEW",
                    owner_user_id=user.id,
                )
                self.db.add(org)
            else:
                org.name = company_name
                org.domain = domain
                org.country = country
                org.team_size = team_size
                org.phone_number = phone_number
                org.address = address
                org.selected_doc_category = doc_category
                org.document_name = doc_name
                org.document_number = doc_number
                if doc_file_url:
                    org.document_file_url = doc_file_url
                if discussion_date:
                    org.discussion_date = discussion_date
                if discussion_time:
                    org.discussion_time = discussion_time
                if discussion_timezone:
                    org.discussion_timezone = discussion_timezone
                if meet_link:
                    org.meet_link = meet_link
                org.use_case = use_case
                org.status = "PENDING_REVIEW"
                org.updated_at = datetime.now(timezone.utc)

            user.onboarding_state = "PENDING_VERIFICATION"
            user.updated_at = datetime.now(timezone.utc)

            # Flush org to ensure org.id is generated
            await self.db.flush()

            event = OnboardingEvent(
                org_id=org.id,
                from_state=from_state,
                to_state="PENDING_VERIFICATION",
                triggered_by=user.email,
                metadata_json={
                    "country": country,
                    "doc_category": doc_category,
                    "doc_name": doc_name,
                    "discussion_date": discussion_date,
                    "discussion_time": discussion_time,
                    "meet_link": meet_link,
                    "use_case": use_case,
                },
            )
            self.db.add(event)
            await self.db.flush()

            # Trigger Admin Email Notification
            from app.services.email_service import (
                send_admin_onboarding_notification,
                send_client_onboarding_notification,
            )
            await send_admin_onboarding_notification(
                company_name=company_name,
                user_email=user.email,
                country=country,
                doc_type=doc_name or "N/A",
                action="SUBMITTED" if from_state != "PENDING_VERIFICATION" else "UPDATED",
                discussion_date=discussion_date,
                discussion_time=discussion_time,
                meet_link=meet_link,
            )

            # Trigger Client Email Notification
            await send_client_onboarding_notification(
                company_name=company_name,
                client_email=user.email,
                country=country,
                discussion_date=discussion_date,
                discussion_time=discussion_time,
                meet_link=meet_link,
            )

            logger.info("Client onboarding submitted", extra={"user_id": str(user.id), "org_id": str(org.id)})
            return org

        except Exception as exc:
            user_identifier = getattr(user, "email", "unknown")
            logger.error(f"Failed to submit client onboarding for user {user_identifier}: {exc}")
            raise

    async def get_resume_route(self, user: User) -> dict[str, str]:
        state_route_map = {
            "PENDING_OTP": "/signup",
            "EMAIL_VERIFIED": "/onboarding",
            "PROFILE_INCOMPLETE": "/onboarding",
            "ACTIVE": "/dashboard",
        }
        route = state_route_map.get(user.onboarding_state, "/onboarding")
        return {"state": user.onboarding_state, "redirect_url": route}
