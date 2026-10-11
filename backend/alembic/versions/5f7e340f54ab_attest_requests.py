"""attest requests

Revision ID: 5f7e340f54ab
Revises: 8fcf92f4fbe0
Create Date: 2026-10-11 16:30:14.130938
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = '5f7e340f54ab'
down_revision: Union[str, Sequence[str], None] = '8fcf92f4fbe0'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # When a platform asked for its imported records to count as verified.
    op.add_column('platform_keys', sa.Column('attest_requested_at', sa.DateTime(timezone=True), nullable=True))


def downgrade() -> None:
    op.drop_column('platform_keys', 'attest_requested_at')
