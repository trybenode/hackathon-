"""platform key environments

Revision ID: 34758bfdd3a2
Revises: 2abdca2ad760
Create Date: 2026-10-10 14:25:18.277534
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = '34758bfdd3a2'
down_revision: Union[str, Sequence[str], None] = '2abdca2ad760'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Keys issued before environments existed are production keys.
    op.add_column('platform_keys', sa.Column('environment', sa.String(length=20), server_default='production', nullable=False))
    op.add_column('platform_keys', sa.Column('key_id', sa.String(length=40), nullable=True))
    op.add_column('platform_keys', sa.Column('created_by_user_id', sa.Uuid(), nullable=True))
    op.create_unique_constraint(op.f('uq_platform_keys_key_id'), 'platform_keys', ['key_id'])
    op.create_foreign_key(op.f('fk_platform_keys_created_by_user_id_users'), 'platform_keys', 'users', ['created_by_user_id'], ['id'], ondelete='SET NULL')


def downgrade() -> None:
    op.drop_constraint(op.f('fk_platform_keys_created_by_user_id_users'), 'platform_keys', type_='foreignkey')
    op.drop_constraint(op.f('uq_platform_keys_key_id'), 'platform_keys', type_='unique')
    op.drop_column('platform_keys', 'created_by_user_id')
    op.drop_column('platform_keys', 'key_id')
    op.drop_column('platform_keys', 'environment')
