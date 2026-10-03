"""Purpose: Add guarantor contact details and the KYC document reference.

Dependencies: Alembic.
Used by: `alembic upgrade head`.

Revision ID: a27e91b4c6d5
Revises: f1a6c0d34b87
Create Date: 2026-09-30
"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "a27e91b4c6d5"
down_revision: Union[str, Sequence[str], None] = "f1a6c0d34b87"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column("users", sa.Column("phone", sa.String(length=40), nullable=True))
    op.add_column("users", sa.Column("address", sa.String(length=500), nullable=True))
    op.add_column(
        "identity_verifications",
        sa.Column("document_reference", sa.String(length=500), nullable=True),
    )


def downgrade() -> None:
    op.drop_column("identity_verifications", "document_reference")
    op.drop_column("users", "address")
    op.drop_column("users", "phone")
