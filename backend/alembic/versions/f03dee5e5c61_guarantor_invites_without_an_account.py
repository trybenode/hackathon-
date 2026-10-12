"""guarantor invites without an account

Revision ID: f03dee5e5c61
Revises: f69a915488e3
Create Date: 2026-10-10 11:09:58.738880
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = 'f03dee5e5c61'
down_revision: Union[str, Sequence[str], None] = 'f69a915488e3'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # A worker's invite link has no guarantor account until someone claims it.
    op.add_column('guarantor_agreements', sa.Column('guarantor_name', sa.String(length=160), nullable=True))
    op.alter_column('guarantor_agreements', 'guarantor_user_id', existing_type=sa.UUID(), nullable=True)


def downgrade() -> None:
    # Unclaimed invites cannot satisfy the old constraint.
    op.execute("DELETE FROM guarantor_agreements WHERE guarantor_user_id IS NULL")
    op.alter_column('guarantor_agreements', 'guarantor_user_id', existing_type=sa.UUID(), nullable=False)
    op.drop_column('guarantor_agreements', 'guarantor_name')
