"""Purpose: Add guarantor instrument lifecycle states and instrument detail columns.

Dependencies: Alembic and PostgreSQL enum alteration.
Used by: `alembic upgrade head` against the shared Neon database.

Revision ID: b7c41d9e2a08
Revises: f0282d29c035
Create Date: 2026-09-29
"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "b7c41d9e2a08"
down_revision: Union[str, Sequence[str], None] = "f0282d29c035"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

NEW_STATUSES = ("draft", "pending_signature", "triggered")


def upgrade() -> None:
    # Postgres cannot drop enum values, so new lifecycle states are added
    # alongside the existing ones. IF NOT EXISTS keeps the step re-runnable.
    for value in NEW_STATUSES:
        op.execute(f"ALTER TYPE agreement_status ADD VALUE IF NOT EXISTS '{value}'")

    op.add_column(
        "guarantor_agreements",
        sa.Column("guarantor_phone", sa.String(length=40), nullable=False, server_default=""),
    )
    op.add_column(
        "guarantor_agreements",
        sa.Column("guarantor_address", sa.String(length=500), nullable=False, server_default=""),
    )
    op.add_column(
        "guarantor_agreements",
        sa.Column("triggered_at", sa.DateTime(timezone=True), nullable=True),
    )
    op.add_column(
        "guarantor_agreements",
        sa.Column("closed_at", sa.DateTime(timezone=True), nullable=True),
    )
    op.add_column(
        "guarantor_agreements",
        sa.Column("status_reason", sa.String(length=500), nullable=True),
    )


def downgrade() -> None:
    op.drop_column("guarantor_agreements", "status_reason")
    op.drop_column("guarantor_agreements", "closed_at")
    op.drop_column("guarantor_agreements", "triggered_at")
    op.drop_column("guarantor_agreements", "guarantor_address")
    op.drop_column("guarantor_agreements", "guarantor_phone")
    # The added enum values are left in place: Postgres cannot remove them
    # without rewriting the type, and no row can reference them after the
    # instruments above are gone.
