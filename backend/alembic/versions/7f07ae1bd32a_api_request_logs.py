"""api request logs

Revision ID: 7f07ae1bd32a
Revises: bc91bab20aef
Create Date: 2026-10-10 14:26:04.409918
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = '7f07ae1bd32a'
down_revision: Union[str, Sequence[str], None] = 'bc91bab20aef'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Calls made with platform keys, for the developer dashboard. No bodies.
    op.create_table('api_request_logs',
    sa.Column('platform_key_id', sa.Uuid(), nullable=False),
    sa.Column('organization_id', sa.Uuid(), nullable=False),
    sa.Column('method', sa.String(length=10), nullable=False),
    sa.Column('path', sa.String(length=300), nullable=False),
    sa.Column('status_code', sa.Integer(), nullable=False),
    sa.Column('duration_ms', sa.Integer(), nullable=False),
    sa.Column('id', sa.Uuid(), nullable=False),
    sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
    sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
    sa.ForeignKeyConstraint(['organization_id'], ['organizations.id'], name=op.f('fk_api_request_logs_organization_id_organizations'), ondelete='CASCADE'),
    sa.ForeignKeyConstraint(['platform_key_id'], ['platform_keys.id'], name=op.f('fk_api_request_logs_platform_key_id_platform_keys'), ondelete='CASCADE'),
    sa.PrimaryKeyConstraint('id', name=op.f('pk_api_request_logs'))
    )
    op.create_index(op.f('ix_api_request_logs_organization_id'), 'api_request_logs', ['organization_id'], unique=False)
    op.create_index(op.f('ix_api_request_logs_platform_key_id'), 'api_request_logs', ['platform_key_id'], unique=False)


def downgrade() -> None:
    op.drop_index(op.f('ix_api_request_logs_platform_key_id'), table_name='api_request_logs')
    op.drop_index(op.f('ix_api_request_logs_organization_id'), table_name='api_request_logs')
    op.drop_table('api_request_logs')
