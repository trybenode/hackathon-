"""Portable history, consent and restricted reviews (additive)."""
from alembic import op
import sqlalchemy as sa

revision = "8f41c20a9e37"
down_revision = "6c4e91a2d7f0"
branch_labels = None
depends_on = None


def upgrade():

    op.add_column('jobs', sa.Column('client_id', sa.Uuid(), nullable=True))
    op.add_column('normalized_outcomes', sa.Column('available_signals', sa.JSON(), nullable=True))
    op.add_column('normalized_outcomes', sa.Column('verification_method', sa.String(length=40), nullable=True))
    op.add_column('normalized_outcomes', sa.Column('verified_by_org_id', sa.Uuid(), nullable=True))
    op.add_column('normalized_outcomes', sa.Column('verified_at', sa.DateTime(timezone=True), nullable=True))
    op.create_foreign_key(op.f('fk_jobs_client_id_users'), 'jobs', 'users', ['client_id'], ['id'], ondelete='RESTRICT')
    op.create_foreign_key(op.f('fk_normalized_outcomes_verified_by_org_id_organizations'), 'normalized_outcomes', 'organizations', ['verified_by_org_id'], ['id'], ondelete='RESTRICT')
    op.create_table('platform_keys',
    sa.Column('organization_id', sa.Uuid(), nullable=False),
    sa.Column('key_hash', sa.String(length=64), nullable=False),
    sa.Column('can_attest', sa.Boolean(), nullable=False),
    sa.Column('revoked_at', sa.DateTime(timezone=True), nullable=True),
    sa.Column('id', sa.Uuid(), nullable=False),
    sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
    sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
    sa.ForeignKeyConstraint(['organization_id'], ['organizations.id'], name=op.f('fk_platform_keys_organization_id_organizations'), ondelete='CASCADE'),
    sa.PrimaryKeyConstraint('id', name=op.f('pk_platform_keys')),
    sa.UniqueConstraint('key_hash', name=op.f('uq_platform_keys_key_hash'))
    )
    op.create_table('import_receipts',
    sa.Column('organization_id', sa.Uuid(), nullable=False),
    sa.Column('worker_id', sa.Uuid(), nullable=False),
    sa.Column('idempotency_key', sa.String(length=128), nullable=False),
    sa.Column('payload_hash', sa.String(length=64), nullable=False),
    sa.Column('result', sa.JSON(), nullable=False),
    sa.Column('id', sa.Uuid(), nullable=False),
    sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
    sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
    sa.ForeignKeyConstraint(['organization_id'], ['organizations.id'], name=op.f('fk_import_receipts_organization_id_organizations'), ondelete='CASCADE'),
    sa.ForeignKeyConstraint(['worker_id'], ['workers.id'], name=op.f('fk_import_receipts_worker_id_workers'), ondelete='CASCADE'),
    sa.PrimaryKeyConstraint('id', name=op.f('pk_import_receipts')),
    sa.UniqueConstraint('organization_id', 'idempotency_key', name=op.f('uq_import_receipts_organization_id'))
    )
    op.create_table('platform_grants',
    sa.Column('worker_id', sa.Uuid(), nullable=False),
    sa.Column('organization_id', sa.Uuid(), nullable=False),
    sa.Column('token_hash', sa.String(length=64), nullable=False),
    sa.Column('permissions', sa.JSON(), nullable=False),
    sa.Column('expires_at', sa.DateTime(timezone=True), nullable=False),
    sa.Column('revoked_at', sa.DateTime(timezone=True), nullable=True),
    sa.Column('id', sa.Uuid(), nullable=False),
    sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
    sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
    sa.ForeignKeyConstraint(['organization_id'], ['organizations.id'], name=op.f('fk_platform_grants_organization_id_organizations'), ondelete='CASCADE'),
    sa.ForeignKeyConstraint(['worker_id'], ['workers.id'], name=op.f('fk_platform_grants_worker_id_workers'), ondelete='CASCADE'),
    sa.PrimaryKeyConstraint('id', name=op.f('pk_platform_grants')),
    sa.UniqueConstraint('token_hash', name=op.f('uq_platform_grants_token_hash'))
    )
    op.create_index(op.f('ix_platform_grants_worker_id'), 'platform_grants', ['worker_id'], unique=False)
    op.create_table('share_grants',
    sa.Column('worker_id', sa.Uuid(), nullable=False),
    sa.Column('token_hash', sa.String(length=64), nullable=False),
    sa.Column('expires_at', sa.DateTime(timezone=True), nullable=False),
    sa.Column('revoked_at', sa.DateTime(timezone=True), nullable=True),
    sa.Column('id', sa.Uuid(), nullable=False),
    sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
    sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
    sa.ForeignKeyConstraint(['worker_id'], ['workers.id'], name=op.f('fk_share_grants_worker_id_workers'), ondelete='CASCADE'),
    sa.PrimaryKeyConstraint('id', name=op.f('pk_share_grants')),
    sa.UniqueConstraint('token_hash', name=op.f('uq_share_grants_token_hash'))
    )
    op.create_index(op.f('ix_share_grants_worker_id'), 'share_grants', ['worker_id'], unique=False)
    op.create_table('reviews',
    sa.Column('job_id', sa.Uuid(), nullable=False),
    sa.Column('reviewer_id', sa.Uuid(), nullable=False),
    sa.Column('identity_verification_id', sa.Uuid(), nullable=False),
    sa.Column('rating', sa.Integer(), nullable=False),
    sa.Column('comment', sa.Text(), nullable=True),
    sa.Column('idempotency_key', sa.String(length=128), nullable=False),
    sa.Column('payload_hash', sa.String(length=64), nullable=False),
    sa.Column('id', sa.Uuid(), nullable=False),
    sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
    sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
    sa.CheckConstraint('rating BETWEEN 1 AND 5', name=op.f('ck_reviews_review_rating_range')),
    sa.ForeignKeyConstraint(['identity_verification_id'], ['identity_verifications.id'], name=op.f('fk_reviews_identity_verification_id_identity_verifications'), ondelete='RESTRICT'),
    sa.ForeignKeyConstraint(['job_id'], ['jobs.id'], name=op.f('fk_reviews_job_id_jobs'), ondelete='RESTRICT'),
    sa.ForeignKeyConstraint(['reviewer_id'], ['users.id'], name=op.f('fk_reviews_reviewer_id_users'), ondelete='RESTRICT'),
    sa.PrimaryKeyConstraint('id', name=op.f('pk_reviews')),
    sa.UniqueConstraint('job_id', name=op.f('uq_reviews_job_id'))
    )
    op.create_index(op.f('ix_reviews_reviewer_id'), 'reviews', ['reviewer_id'], unique=False)
    op.create_table('worker_links',
    sa.Column('organization_id', sa.Uuid(), nullable=False),
    sa.Column('worker_id', sa.Uuid(), nullable=False),
    sa.Column('external_worker_id', sa.String(length=120), nullable=False),
    sa.Column('grant_id', sa.Uuid(), nullable=False),
    sa.Column('id', sa.Uuid(), nullable=False),
    sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
    sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
    sa.ForeignKeyConstraint(['grant_id'], ['platform_grants.id'], name=op.f('fk_worker_links_grant_id_platform_grants'), ondelete='CASCADE'),
    sa.ForeignKeyConstraint(['organization_id'], ['organizations.id'], name=op.f('fk_worker_links_organization_id_organizations'), ondelete='CASCADE'),
    sa.ForeignKeyConstraint(['worker_id'], ['workers.id'], name=op.f('fk_worker_links_worker_id_workers'), ondelete='CASCADE'),
    sa.PrimaryKeyConstraint('id', name=op.f('pk_worker_links')),
    sa.UniqueConstraint('organization_id', 'external_worker_id', name=op.f('uq_worker_links_organization_id'))
    )
    op.create_table('history_identities',
    sa.Column('worker_id', sa.Uuid(), nullable=False),
    sa.Column('organization_id', sa.Uuid(), nullable=False),
    sa.Column('source_record_id', sa.String(length=80), nullable=False),
    sa.Column('payload_hash', sa.String(length=64), nullable=False),
    sa.Column('outcome_id', sa.Uuid(), nullable=False),
    sa.Column('id', sa.Uuid(), nullable=False),
    sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
    sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
    sa.ForeignKeyConstraint(['organization_id'], ['organizations.id'], name=op.f('fk_history_identities_organization_id_organizations'), ondelete='RESTRICT'),
    sa.ForeignKeyConstraint(['outcome_id'], ['normalized_outcomes.id'], name=op.f('fk_history_identities_outcome_id_normalized_outcomes'), ondelete='CASCADE'),
    sa.ForeignKeyConstraint(['worker_id'], ['workers.id'], name=op.f('fk_history_identities_worker_id_workers'), ondelete='CASCADE'),
    sa.PrimaryKeyConstraint('id', name=op.f('pk_history_identities')),
    sa.UniqueConstraint('worker_id', 'organization_id', 'source_record_id', name=op.f('uq_history_identities_worker_id'))
    )



def downgrade():

    op.drop_table('history_identities')
    op.drop_table('worker_links')
    op.drop_index(op.f('ix_reviews_reviewer_id'), table_name='reviews')
    op.drop_table('reviews')
    op.drop_index(op.f('ix_share_grants_worker_id'), table_name='share_grants')
    op.drop_table('share_grants')
    op.drop_index(op.f('ix_platform_grants_worker_id'), table_name='platform_grants')
    op.drop_table('platform_grants')
    op.drop_table('import_receipts')
    op.drop_table('platform_keys')
    op.drop_column('normalized_outcomes', 'verified_at')
    op.drop_column('normalized_outcomes', 'verified_by_org_id')
    op.drop_column('normalized_outcomes', 'verification_method')
    op.drop_column('normalized_outcomes', 'available_signals')
    op.drop_column('jobs', 'client_id')

