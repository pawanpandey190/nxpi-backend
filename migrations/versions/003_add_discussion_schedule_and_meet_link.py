"""Add discussion schedule and meet link columns to organizations table

Revision ID: 003
Revises: 002
Create Date: 2026-08-14

"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "003"
down_revision: Union[str, None] = "002"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column("organizations", sa.Column("discussion_date", sa.String(50), nullable=True))
    op.add_column("organizations", sa.Column("discussion_time", sa.String(50), nullable=True))
    op.add_column("organizations", sa.Column("discussion_timezone", sa.String(100), nullable=True))
    op.add_column("organizations", sa.Column("meet_link", sa.String(500), nullable=True))


def downgrade() -> None:
    op.drop_column("organizations", "meet_link")
    op.drop_column("organizations", "discussion_timezone")
    op.drop_column("organizations", "discussion_time")
    op.drop_column("organizations", "discussion_date")
