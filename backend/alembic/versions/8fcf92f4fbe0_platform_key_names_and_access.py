"""platform key names and access

Revision ID: 8fcf92f4fbe0
Revises: 46c1bd5f370d
Create Date: 2026-10-11 15:32:26.458763
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = '8fcf92f4fbe0'
down_revision: Union[str, Sequence[str], None] = '46c1bd5f370d'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Existing keys keep full access (no scopes) and have no name.
    op.add_column('platform_keys', sa.Column('name', sa.String(length=80), nullable=True))
    op.add_column('platform_keys', sa.Column('scopes', sa.JSON(), nullable=True))
    op.add_column('platform_keys', sa.Column('last_used_at', sa.DateTime(timezone=True), nullable=True))


def downgrade() -> None:
    op.drop_column('platform_keys', 'last_used_at')
    op.drop_column('platform_keys', 'scopes')
    op.drop_column('platform_keys', 'name')
