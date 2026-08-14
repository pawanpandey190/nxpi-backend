"""
Contact form API endpoint.
"""

import logging
from typing import Optional
from fastapi import APIRouter, status
from pydantic import BaseModel, EmailStr

from app.services.email_service import send_contact_sales_email

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/contact", tags=["Contact"])


class ContactRequest(BaseModel):
    name: str
    email: EmailStr
    company: str
    phone: Optional[str] = None
    role: str
    intent: str
    message: Optional[str] = None


@router.post(
    "/submit",
    status_code=status.HTTP_200_OK,
    summary="Submit a contact or sales inquiry",
)
async def submit_contact_inquiry(payload: ContactRequest) -> dict:
    try:
        await send_contact_sales_email(
            name=payload.name,
            email=payload.email,
            company=payload.company,
            phone=payload.phone,
            role=payload.role,
            intent=payload.intent,
            message=payload.message,
        )
        return {"status": "success", "message": "Inquiry submitted successfully"}
    except Exception as exc:
        logger.error(f"Failed to submit contact inquiry: {exc}")
        return {"status": "error", "message": "Failed to submit inquiry"}
