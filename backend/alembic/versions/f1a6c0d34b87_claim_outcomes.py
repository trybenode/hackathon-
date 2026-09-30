"""Purpose: Add claim outcome states to the guarantor lifecycle.

Dependencies: Alembic and PostgreSQL enum alteration.
Used by: `alembic upgrade head`.

Revision ID: f1a6c0d34b87
Revises: e5b73c81f402
Create Date: 2026-09-30
"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "f1a6c0d34b87"
down_revision: Union[str, Sequence[str], None] = "e5b73c81f402"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

# Upper-case to match SQLAlchemy's name-based enum storage.
NEW_STATUSES = ("DISPUTED", "PAID", "DISMISSED")


def upgrade() -> None:
    for value in NEW_STATUSES:
        op.execute(f"ALTER TYPE agreement_status ADD VALUE IF NOT EXISTS '{value}'")

    op.add_column(
        "guarantor_agreements",
        sa.Column("resolved_at", sa.DateTime(timezone=True), nullable=True),
    )


def downgrade() -> None:
    op.drop_column("guarantor_agreements", "resolved_at")
    # Postgres cannot drop enum labels; they are left in place.
