"""escrow through payscrow

Revision ID: c813a0a357fc
Revises: 1d7fe6fb9d97
Create Date: 2026-10-08 11:44:35.578148
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = 'c813a0a357fc'
down_revision: Union[str, Sequence[str], None] = '1d7fe6fb9d97'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Everything is nullable or defaulted: jobs and escrows that predate
    # Payscrow simply have none of it.
    op.add_column('escrow_transactions', sa.Column('provider_transaction_id', sa.String(length=64), nullable=True))
    op.add_column('escrow_transactions', sa.Column('payment_link', sa.String(length=500), nullable=True))
    op.add_column('escrow_transactions', sa.Column('total_payable', sa.Numeric(precision=12, scale=2), nullable=True))
    op.add_column('escrow_transactions', sa.Column('funded_at', sa.DateTime(timezone=True), nullable=True))
    op.add_column('escrow_transactions', sa.Column('released_at', sa.DateTime(timezone=True), nullable=True))
    op.add_column('escrow_transactions', sa.Column('in_dispute', sa.Boolean(), server_default='false', nullable=False))
    op.add_column('escrow_transactions', sa.Column('dispute_stage', sa.String(length=40), nullable=True))
    op.add_column('escrow_transactions', sa.Column('resolution_type', sa.String(length=20), nullable=True))
    op.add_column('jobs', sa.Column('client_name', sa.String(length=300), nullable=True))
    op.add_column('jobs', sa.Column('client_email', sa.String(length=320), nullable=True))
    op.add_column('jobs', sa.Column('client_phone', sa.String(length=40), nullable=True))
    op.add_column('jobs', sa.Column('location', sa.String(length=160), nullable=True))
    op.add_column('jobs', sa.Column('details', sa.JSON(), server_default='[]', nullable=False))
    op.add_column('jobs', sa.Column('completed_at', sa.DateTime(timezone=True), nullable=True))
    op.add_column('jobs', sa.Column('confirmation_reminded_at', sa.DateTime(timezone=True), nullable=True))


def downgrade() -> None:
    op.drop_column('jobs', 'confirmation_reminded_at')
    op.drop_column('jobs', 'completed_at')
    op.drop_column('jobs', 'details')
    op.drop_column('jobs', 'location')
    op.drop_column('jobs', 'client_phone')
    op.drop_column('jobs', 'client_email')
    op.drop_column('jobs', 'client_name')
    op.drop_column('escrow_transactions', 'resolution_type')
    op.drop_column('escrow_transactions', 'dispute_stage')
    op.drop_column('escrow_transactions', 'in_dispute')
    op.drop_column('escrow_transactions', 'released_at')
    op.drop_column('escrow_transactions', 'funded_at')
    op.drop_column('escrow_transactions', 'total_payable')
    op.drop_column('escrow_transactions', 'payment_link')
    op.drop_column('escrow_transactions', 'provider_transaction_id')
