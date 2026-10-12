"""sandbox workers

Revision ID: bc91bab20aef
Revises: 34758bfdd3a2
Create Date: 2026-10-10 14:25:42.376657
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = 'bc91bab20aef'
down_revision: Union[str, Sequence[str], None] = '34758bfdd3a2'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Every existing worker is real.
    op.add_column('workers', sa.Column('is_sandbox', sa.Boolean(), server_default='false', nullable=False))


def downgrade() -> None:
    op.drop_column('workers', 'is_sandbox')
