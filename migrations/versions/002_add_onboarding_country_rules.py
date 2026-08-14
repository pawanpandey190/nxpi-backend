"""Add country document rules and onboarding fields

Revision ID: 002
Revises: 001
Create Date: 2026-08-12

"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "002"
down_revision: Union[str, None] = "001"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

COUNTRY_RULES_DATA = [
    ("IN", "India", "CIN / LLPIN / Registration No.", "PAN", "GSTIN"),
    ("US", "USA", "State Registration No.", "EIN", "State Sales Tax ID"),
    ("GB", "UK", "CRN", "UTR", "VAT"),
    ("CA", "Canada", "BN / Provincial No.", "BN / CRA ID", "GST/HST"),
    ("AU", "Australia", "ACN / ABN", "Tax ID / ABN", "GST"),
    ("SG", "Singapore", "UEN", "Tax ID", "GST"),
    ("AE", "UAE", "Trade Licence / CR", "Tax ID / Corporate Tax", "VAT TRN"),
    ("DE", "Germany", "Handelsregister No.", "Steuernummer / W-IdNr.", "VAT ID"),
    ("FR", "France", "SIREN / SIRET", "Tax ID", "VAT ID"),
    ("IT", "Italy", "Registro Imprese / REA", "Codice Fiscale", "Partita IVA"),
    ("ES", "Spain", "Registro Mercantil", "NIF", "VAT"),
    ("NL", "Netherlands", "KvK No.", "Tax ID", "VAT"),
    ("CH", "Switzerland", "UID/CHE", "Tax ID", "VAT"),
    ("JP", "Japan", "Corporate Number", "Tax ID", "Consumption Tax"),
    ("CN", "China", "USCC", "Tax ID", "VAT"),
    ("HK", "Hong Kong", "Company No.", "BRN / Tax ID", "No general VAT/GST"),
    ("KR", "South Korea", "Corporate No.", "Business Registration No.", "VAT"),
    ("MY", "Malaysia", "SSM Registration No.", "TIN", "SST"),
    ("ID", "Indonesia", "NIB", "NPWP", "VAT/PKP"),
    ("TH", "Thailand", "Company Registration No.", "Tax ID", "VAT"),
    ("VN", "Vietnam", "Enterprise Registration No.", "Tax ID", "VAT"),
    ("PH", "Philippines", "SEC Registration No.", "TIN", "VAT"),
    ("NZ", "New Zealand", "NZBN / Company No.", "IRD No.", "GST"),
    ("ZA", "South Africa", "CIPC No.", "Tax Reference No.", "VAT"),
    ("BR", "Brazil", "CNPJ", "CNPJ / Tax ID", "ICMS / ISS"),
    ("MX", "Mexico", "Company Registration", "RFC", "IVA/VAT"),
    ("SA", "Saudi Arabia", "Commercial Registration No.", "Tax ID", "VAT"),
    ("IE", "Ireland", "CRO No.", "Tax Reference No.", "VAT"),
]


def upgrade() -> None:
    # ── 1. Create country_document_rules table ────────────────────────────────
    op.create_table(
        "country_document_rules",
        sa.Column(
            "id",
            postgresql.UUID(as_uuid=True),
            server_default=sa.text("gen_random_uuid()"),
            nullable=False,
        ),
        sa.Column("country_code", sa.String(10), nullable=False),
        sa.Column("country_name", sa.String(100), nullable=False),
        sa.Column("company_registration_label", sa.String(255), nullable=False),
        sa.Column("tax_identity_label", sa.String(255), nullable=False),
        sa.Column("indirect_tax_label", sa.String(255), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("NOW()"),
            nullable=False,
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("country_code", name="uq_country_code"),
    )
    op.create_index("idx_country_rules_code", "country_document_rules", ["country_code"])
    op.create_index("idx_country_rules_name", "country_document_rules", ["country_name"])

    # ── 2. Add Onboarding fields to organizations table ────────────────────────
    op.add_column("organizations", sa.Column("country", sa.String(100), nullable=True))
    op.add_column("organizations", sa.Column("address", sa.Text(), nullable=True))
    op.add_column("organizations", sa.Column("phone_number", sa.String(50), nullable=True))
    op.add_column("organizations", sa.Column("selected_doc_category", sa.String(100), nullable=True))
    op.add_column("organizations", sa.Column("document_name", sa.String(255), nullable=True))
    op.add_column("organizations", sa.Column("document_number", sa.String(255), nullable=True))
    op.add_column("organizations", sa.Column("document_file_url", sa.String(500), nullable=True))

    # ── 3. Seed 28 countries ──────────────────────────────────────────────────
    country_table = sa.table(
        "country_document_rules",
        sa.column("country_code", sa.String),
        sa.column("country_name", sa.String),
        sa.column("company_registration_label", sa.String),
        sa.column("tax_identity_label", sa.String),
        sa.column("indirect_tax_label", sa.String),
    )

    op.bulk_insert(
        country_table,
        [
            {
                "country_code": code,
                "country_name": name,
                "company_registration_label": comp,
                "tax_identity_label": tax,
                "indirect_tax_label": ind_tax,
            }
            for code, name, comp, tax, ind_tax in COUNTRY_RULES_DATA
        ],
    )


def downgrade() -> None:
    op.drop_column("organizations", "document_file_url")
    op.drop_column("organizations", "document_number")
    op.drop_column("organizations", "document_name")
    op.drop_column("organizations", "selected_doc_category")
    op.drop_column("organizations", "phone_number")
    op.drop_column("organizations", "address")
    op.drop_column("organizations", "country")
    op.drop_table("country_document_rules")
