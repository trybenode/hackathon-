"""Independent history claims and scoped customer attribution.

Revision ID: a81c2d43e9f0; revises c735ab42f6d0.
"""
import sqlalchemy as sa
from alembic import op
revision = "a81c2d43e9f0"
down_revision = "c735ab42f6d0"
branch_labels = None
depends_on = None


def base_columns():
    return [sa.Column("id", sa.Uuid(), primary_key=True), sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False), sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False)]


def upgrade():
    op.create_table("history_claims", *base_columns(),
        sa.Column("worker_id", sa.Uuid(), sa.ForeignKey("workers.id", ondelete="RESTRICT"), nullable=False),
        sa.Column("job_id", sa.Uuid(), sa.ForeignKey("jobs.id", ondelete="RESTRICT")),
        sa.Column("operation_id", sa.Uuid(), nullable=False), sa.Column("payload_hash", sa.String(64), nullable=False),
        sa.Column("revision", sa.Integer(), nullable=False), sa.Column("details", sa.JSON(), nullable=False),
        sa.Column("archived_at", sa.DateTime(timezone=True)),
        sa.UniqueConstraint("worker_id", "operation_id", name="uq_history_claims_worker_operation"), sa.UniqueConstraint("worker_id", "job_id", name="uq_history_claims_worker_job"),
        sa.CheckConstraint("revision > 0", name="positive_revision"))
    op.create_index("ix_history_claims_worker_id", "history_claims", ["worker_id"])
    op.create_table("history_confirmation_requests", *base_columns(),
        sa.Column("claim_id", sa.Uuid(), sa.ForeignKey("history_claims.id", ondelete="RESTRICT"), nullable=False),
        sa.Column("operation_id", sa.Uuid(), nullable=False), sa.Column("payload_hash", sa.String(64), nullable=False),
        sa.Column("revision", sa.Integer(), nullable=False), sa.Column("snapshot", sa.JSON(), nullable=False),
        sa.Column("recipient_phone", sa.String(20)), sa.Column("hiring_customer_id", sa.Uuid(), sa.ForeignKey("users.id", ondelete="RESTRICT")), sa.Column("token_hash", sa.String(64), unique=True, nullable=False),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=False), sa.Column("revoked_at", sa.DateTime(timezone=True)),
        sa.Column("challenge_hash", sa.String(64)), sa.Column("challenge_reference", sa.String(160)),
        sa.Column("challenge_expires_at", sa.DateTime(timezone=True)), sa.Column("challenge_sent_at", sa.DateTime(timezone=True)),
        sa.Column("challenge_send_count", sa.Integer(), nullable=False), sa.Column("challenge_attempts", sa.Integer(), nullable=False), sa.Column("challenge_sandbox", sa.Boolean(), nullable=False),
        sa.Column("session_hash", sa.String(64)), sa.Column("session_expires_at", sa.DateTime(timezone=True)),
        sa.UniqueConstraint("claim_id", "operation_id"))
    op.create_index("ix_history_confirmation_requests_claim_id", "history_confirmation_requests", ["claim_id"])
    op.create_table("history_customer_responses", *base_columns(),
        sa.Column("request_id", sa.Uuid(), sa.ForeignKey("history_confirmation_requests.id", ondelete="RESTRICT"), nullable=False, unique=True),
        sa.Column("actor_id", sa.Uuid(), sa.ForeignKey("users.id", ondelete="RESTRICT")),
        sa.Column("operation_id", sa.Uuid(), nullable=False), sa.Column("payload_hash", sa.String(64), nullable=False),
        sa.Column("decision", sa.String(30), nullable=False), sa.Column("declares_customer", sa.Boolean(), nullable=False), sa.Column("attribution", sa.String(40), nullable=False),
        sa.Column("sandbox", sa.Boolean(), nullable=False), sa.Column("withdrawn_at", sa.DateTime(timezone=True)))


def downgrade():
    for table in ("history_customer_responses", "history_confirmation_requests", "history_claims"):
        op.drop_table(table)
