"""
CountryDocumentRule ORM model.
Stores country-specific compliance document rules.
"""

import uuid
from datetime import datetime, timezone

from sqlalchemy import DateTime, String, func, text
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.core.config import settings
from app.core.database import Base


class CountryDocumentRule(Base):
    __tablename__ = "country_document_rules"
    __table_args__ = {"schema": settings.DATABASE_SCHEMA}

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        primary_key=True,
        server_default=text("gen_random_uuid()"),
        default=uuid.uuid4,
    )
    country_code: Mapped[str] = mapped_column(String(10), unique=True, nullable=False, index=True)
    country_name: Mapped[str] = mapped_column(String(100), nullable=False, index=True)

    company_registration_label: Mapped[str] = mapped_column(String(255), nullable=False)
    tax_identity_label: Mapped[str] = mapped_column(String(255), nullable=False)
    indirect_tax_label: Mapped[str] = mapped_column(String(255), nullable=False)

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        server_default=func.now(),
        default=lambda: datetime.now(timezone.utc),
    )
