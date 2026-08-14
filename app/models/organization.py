"""
Organization ORM model.
"""

import uuid
from datetime import datetime, timezone

from sqlalchemy import DateTime, ForeignKey, String, Text, func, text
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.config import settings
from app.core.database import Base


class Organization(Base):
    __tablename__ = "organizations"
    __table_args__ = {"schema": settings.DATABASE_SCHEMA}

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        primary_key=True,
        server_default=text("gen_random_uuid()"),
        default=uuid.uuid4,
    )
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    domain: Mapped[str | None] = mapped_column(String(255), nullable=True)
    industry: Mapped[str | None] = mapped_column(String(100), nullable=True)
    team_size: Mapped[str | None] = mapped_column(String(50), nullable=True)
    
    # Expanded Onboarding Fields
    country: Mapped[str | None] = mapped_column(String(100), nullable=True)
    address: Mapped[str | None] = mapped_column(Text, nullable=True)
    phone_number: Mapped[str | None] = mapped_column(String(50), nullable=True)
    
    # Document Compliance Fields
    selected_doc_category: Mapped[str | None] = mapped_column(String(100), nullable=True)
    document_name: Mapped[str | None] = mapped_column(String(255), nullable=True)
    document_number: Mapped[str | None] = mapped_column(String(255), nullable=True)
    document_file_url: Mapped[str | None] = mapped_column(String(500), nullable=True)

    # Discussion Schedule & Automated Google Meet Link
    discussion_date: Mapped[str | None] = mapped_column(String(50), nullable=True)
    discussion_time: Mapped[str | None] = mapped_column(String(50), nullable=True)
    discussion_timezone: Mapped[str | None] = mapped_column(String(100), nullable=True)
    meet_link: Mapped[str | None] = mapped_column(String(500), nullable=True)
    use_case: Mapped[str | None] = mapped_column(Text, nullable=True)

    status: Mapped[str] = mapped_column(
        String(50), nullable=False, default="PROFILE_INCOMPLETE", server_default="PROFILE_INCOMPLETE"
    )

    owner_user_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey(f"{settings.DATABASE_SCHEMA}.users.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        server_default=func.now(),
        default=lambda: datetime.now(timezone.utc),
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        server_default=func.now(),
        default=lambda: datetime.now(timezone.utc),
        onupdate=lambda: datetime.now(timezone.utc),
    )

    owner: Mapped["User"] = relationship("User", back_populates="organizations")  # noqa: F821
    events: Mapped[list["OnboardingEvent"]] = relationship(  # noqa: F821
        "OnboardingEvent", back_populates="organization", cascade="all, delete-orphan"
    )
    members: Mapped[list["OrgMember"]] = relationship(  # noqa: F821
        "OrgMember", back_populates="organization", cascade="all, delete-orphan"
    )
