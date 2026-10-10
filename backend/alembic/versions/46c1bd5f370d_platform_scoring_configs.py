"""platform scoring configs

Revision ID: 46c1bd5f370d
Revises: 79938cf43af0
Create Date: 2026-10-10 19:44:09.176687
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = '46c1bd5f370d'
down_revision: Union[str, Sequence[str], None] = '79938cf43af0'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # A platform's own scoring settings per environment and platform type.
    op.create_table('scoring_configs',
    sa.Column('organization_id', sa.Uuid(), nullable=False),
    sa.Column('environment', sa.String(length=20), nullable=False),
    sa.Column('platform_type', sa.String(length=40), nullable=False),
    sa.Column('weights', sa.JSON(), nullable=False),
    sa.Column('required_signals', sa.JSON(), nullable=False),
    sa.Column('hard_fail', sa.JSON(), nullable=False),
    sa.Column('min_jobs', sa.Integer(), nullable=False),
    sa.Column('high_threshold', sa.Float(), nullable=False),
    sa.Column('medium_threshold', sa.Float(), nullable=False),
    sa.Column('id', sa.Uuid(), nullable=False),
    sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
    sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
    sa.ForeignKeyConstraint(['organization_id'], ['organizations.id'], name=op.f('fk_scoring_configs_organization_id_organizations'), ondelete='CASCADE'),
    sa.PrimaryKeyConstraint('id', name=op.f('pk_scoring_configs')),
    sa.UniqueConstraint('organization_id', 'environment', 'platform_type', name=op.f('uq_scoring_configs_organization_id'))
    )
    op.create_index(op.f('ix_scoring_configs_organization_id'), 'scoring_configs', ['organization_id'], unique=False)


def downgrade() -> None:
    op.drop_index(op.f('ix_scoring_configs_organization_id'), table_name='scoring_configs')
    op.drop_table('scoring_configs')
