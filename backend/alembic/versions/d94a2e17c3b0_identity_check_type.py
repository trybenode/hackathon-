"""Purpose: Distinguish identity checks from liveness checks.

Dependencies: Alembic.
Used by: `alembic upgrade head`.

Revision ID: d94a2e17c3b0
Revises: c3f81a5b6d92
Create Date: 2026-09-29
"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "d94a2e17c3b0"
down_revision: Union[str, Sequence[str], None] = "c3f81a5b6d92"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column(
        "identity_verifications",
        sa.Column(
            "check_type",
            sa.String(length=40),
            nullable=False,
            server_default="identity",
        ),
    )


def downgrade() -> None:
    op.drop_column("identity_verifications", "check_type")
