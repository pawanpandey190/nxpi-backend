"""004_add_use_case_column

Add missing use_case column to organizations table.

Revision ID: 004
Revises: 003
Create Date: 2026-08-15
"""

from alembic import op
import sqlalchemy as sa

# revision identifiers
revision = "004"
down_revision = "003"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "organizations",
        sa.Column("use_case", sa.Text(), nullable=True),
        schema="public",
    )


def downgrade() -> None:
    op.drop_column("organizations", "use_case", schema="public")
