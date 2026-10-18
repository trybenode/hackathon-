"""Ownership-reviewed imports and separate onboarding permissions.

Revision ID: a7d01e264c90
Revises: c5b96592228a
"""

from alembic import op
import sqlalchemy as sa

revision = "a7d01e264c90"
down_revision = "c5b96592228a"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "review_memberships",
        sa.Column(
            "user_id",
            sa.Uuid(),
            sa.ForeignKey("users.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("scope", sa.String(length=40), nullable=False),
        sa.Column("environment", sa.String(length=20), nullable=False),
        sa.Column("revoked_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("id", sa.Uuid(), primary_key=True, nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("CURRENT_TIMESTAMP"),
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("CURRENT_TIMESTAMP"),
        ),
        sa.UniqueConstraint(
            "user_id", "scope", "environment", name="uq_review_membership_scope"
        ),
    )
    op.create_table(
        "ownership_imports",
        sa.Column(
            "worker_id",
            sa.Uuid(),
            sa.ForeignKey("workers.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("operation_id", sa.Uuid(), nullable=False),
        sa.Column("payload_hash", sa.String(length=64), nullable=False),
        sa.Column("source_name", sa.String(length=120), nullable=False),
        sa.Column("rows", sa.JSON(), nullable=False),
        sa.Column("state", sa.String(length=30), nullable=False),
        sa.Column("version", sa.Integer(), nullable=False),
        sa.Column(
            "replaces_id",
            sa.Uuid(),
            sa.ForeignKey("ownership_imports.id", ondelete=None),
            nullable=True,
        ),
        sa.Column("document_key", sa.String(length=500), nullable=True),
        sa.Column("document_hash", sa.String(length=64), nullable=True),
        sa.Column("document_type", sa.String(length=40), nullable=True),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("last_reason", sa.Text(), nullable=True),
        sa.Column("id", sa.Uuid(), primary_key=True, nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("CURRENT_TIMESTAMP"),
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("CURRENT_TIMESTAMP"),
        ),
        sa.UniqueConstraint(
            "worker_id", "operation_id", name="uq_ownership_import_operation"
        ),
    )
    op.create_index(
        "ix_ownership_imports_worker_id", "ownership_imports", ["worker_id"]
    )
    op.create_table(
        "provisional_records",
        sa.Column(
            "worker_id",
            sa.Uuid(),
            sa.ForeignKey("workers.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column(
            "batch_id",
            sa.Uuid(),
            sa.ForeignKey("ownership_imports.id", ondelete="RESTRICT"),
            nullable=False,
        ),
        sa.Column("source_key", sa.String(length=64), nullable=False),
        sa.Column("payload_hash", sa.String(length=64), nullable=False),
        sa.Column("details", sa.JSON(), nullable=False),
        sa.Column("id", sa.Uuid(), primary_key=True, nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("CURRENT_TIMESTAMP"),
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("CURRENT_TIMESTAMP"),
        ),
        sa.UniqueConstraint(
            "worker_id", "source_key", name="uq_provisional_source_record"
        ),
    )
    op.create_table(
        "onboarding_policies",
        sa.Column("scope", sa.String(length=40), nullable=False),
        sa.Column("environment", sa.String(length=20), nullable=False),
        sa.Column("platform_type", sa.String(length=30), nullable=False),
        sa.Column("version", sa.Integer(), nullable=False),
        sa.Column("settings", sa.JSON(), nullable=False),
        sa.Column("id", sa.Uuid(), primary_key=True, nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("CURRENT_TIMESTAMP"),
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("CURRENT_TIMESTAMP"),
        ),
        sa.UniqueConstraint(
            "scope", "environment", "platform_type", name="uq_onboarding_policy_scope"
        ),
    )
    op.create_table(
        "onboarding_cases",
        sa.Column(
            "worker_id",
            sa.Uuid(),
            sa.ForeignKey("workers.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("scope", sa.String(length=40), nullable=False),
        sa.Column("environment", sa.String(length=20), nullable=False),
        sa.Column("platform_type", sa.String(length=30), nullable=False),
        sa.Column("version", sa.Integer(), nullable=False),
        sa.Column("policy_version", sa.Integer(), nullable=False),
        sa.Column("evidence_revision", sa.String(length=64), nullable=False),
        sa.Column("state", sa.String(length=30), nullable=False),
        sa.Column("last_reason", sa.Text(), nullable=True),
        sa.Column("worker_response", sa.Text(), nullable=True),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("restrictions", sa.JSON(), nullable=True),
        sa.Column("id", sa.Uuid(), primary_key=True, nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("CURRENT_TIMESTAMP"),
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("CURRENT_TIMESTAMP"),
        ),
        sa.UniqueConstraint(
            "worker_id",
            "scope",
            "environment",
            "platform_type",
            name="uq_onboarding_case_scope",
        ),
    )
    op.create_table(
        "review_decisions",
        sa.Column(
            "actor_id",
            sa.Uuid(),
            sa.ForeignKey("users.id", ondelete="RESTRICT"),
            nullable=False,
        ),
        sa.Column("entity_type", sa.String(length=30), nullable=False),
        sa.Column("entity_id", sa.Uuid(), nullable=False),
        sa.Column("version", sa.Integer(), nullable=False),
        sa.Column("decision", sa.String(length=30), nullable=False),
        sa.Column("reason", sa.Text(), nullable=False),
        sa.Column("evidence_revision", sa.String(length=64), nullable=False),
        sa.Column("policy_version", sa.Integer(), nullable=True),
        sa.Column("id", sa.Uuid(), primary_key=True, nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("CURRENT_TIMESTAMP"),
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("CURRENT_TIMESTAMP"),
        ),
    )


def downgrade() -> None:
    op.drop_table("review_decisions")
    op.drop_table("onboarding_cases")
    op.drop_table("onboarding_policies")
    op.drop_table("provisional_records")
    op.drop_table("ownership_imports")
    op.drop_table("review_memberships")
