"""Purpose: Add the worker profile fields shown on guarantor-facing screens.

Dependencies: Alembic.
Used by: `alembic upgrade head`.

Revision ID: c3f81a5b6d92
Revises: b7c41d9e2a08
Create Date: 2026-09-29
"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "c3f81a5b6d92"
down_revision: Union[str, Sequence[str], None] = "b7c41d9e2a08"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column("workers", sa.Column("role", sa.String(length=80), nullable=True))
    op.add_column("workers", sa.Column("location", sa.String(length=160), nullable=True))
    op.add_column("workers", sa.Column("avatar_url", sa.String(length=500), nullable=True))


def downgrade() -> None:
    op.drop_column("workers", "avatar_url")
    op.drop_column("workers", "location")
    op.drop_column("workers", "role")
