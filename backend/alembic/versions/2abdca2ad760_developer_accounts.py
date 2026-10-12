"""developer accounts

Revision ID: 2abdca2ad760
Revises: c735ab42f6d0
Create Date: 2026-10-10 14:24:41.009111
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = '2abdca2ad760'
down_revision: Union[str, Sequence[str], None] = 'c735ab42f6d0'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # A developer's KYC and KYB, reviewed by an operator, and name-change requests.
    op.create_table('developer_accounts',
    sa.Column('user_id', sa.Uuid(), nullable=False),
    sa.Column('organization_id', sa.Uuid(), nullable=True),
    sa.Column('kyc_status', sa.Enum('NOT_STARTED', 'UNDER_REVIEW', 'APPROVED', 'REJECTED', name='review_status'), nullable=False),
    sa.Column('kyb_status', sa.Enum('NOT_STARTED', 'UNDER_REVIEW', 'APPROVED', 'REJECTED', name='review_status'), nullable=False),
    sa.Column('review_note', sa.String(length=500), nullable=True),
    sa.Column('full_name', sa.String(length=160), nullable=True),
    sa.Column('id_document_type', sa.String(length=40), nullable=True),
    sa.Column('id_document_reference', sa.String(length=500), nullable=True),
    sa.Column('business_name', sa.String(length=200), nullable=True),
    sa.Column('business_type', sa.String(length=40), nullable=True),
    sa.Column('registration_number', sa.String(length=40), nullable=True),
    sa.Column('tax_id', sa.String(length=40), nullable=True),
    sa.Column('cac_document_reference', sa.String(length=500), nullable=True),
    sa.Column('submitted_at', sa.DateTime(timezone=True), nullable=True),
    sa.Column('reviewed_at', sa.DateTime(timezone=True), nullable=True),
    sa.Column('id', sa.Uuid(), nullable=False),
    sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
    sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
    sa.ForeignKeyConstraint(['organization_id'], ['organizations.id'], name=op.f('fk_developer_accounts_organization_id_organizations'), ondelete='SET NULL'),
    sa.ForeignKeyConstraint(['user_id'], ['users.id'], name=op.f('fk_developer_accounts_user_id_users'), ondelete='CASCADE'),
    sa.PrimaryKeyConstraint('id', name=op.f('pk_developer_accounts')),
    sa.UniqueConstraint('user_id', name=op.f('uq_developer_accounts_user_id'))
    )
    op.create_table('developer_name_changes',
    sa.Column('account_id', sa.Uuid(), nullable=False),
    sa.Column('current_name', sa.String(length=160), nullable=False),
    sa.Column('new_name', sa.String(length=160), nullable=False),
    sa.Column('reason', sa.String(length=40), nullable=False),
    sa.Column('document_reference', sa.String(length=500), nullable=True),
    sa.Column('status', sa.Enum('NOT_STARTED', 'UNDER_REVIEW', 'APPROVED', 'REJECTED', name='review_status'), nullable=False),
    sa.Column('reviewed_at', sa.DateTime(timezone=True), nullable=True),
    sa.Column('id', sa.Uuid(), nullable=False),
    sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
    sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
    sa.ForeignKeyConstraint(['account_id'], ['developer_accounts.id'], name=op.f('fk_developer_name_changes_account_id_developer_accounts'), ondelete='CASCADE'),
    sa.PrimaryKeyConstraint('id', name=op.f('pk_developer_name_changes'))
    )
    op.create_index(op.f('ix_developer_name_changes_account_id'), 'developer_name_changes', ['account_id'], unique=False)


def downgrade() -> None:
    op.drop_index(op.f('ix_developer_name_changes_account_id'), table_name='developer_name_changes')
    op.drop_table('developer_name_changes')
    op.drop_table('developer_accounts')
    sa.Enum(name='review_status').drop(op.get_bind(), checkfirst=True)
