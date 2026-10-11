"""Durable transient voice tasks; separate from scored outcomes."""
import sqlalchemy as sa
from alembic import op
revision = "a82c2d43e9f1"
down_revision = "a81c2d43e9f0"
branch_labels = None
depends_on = None


def upgrade():
    op.create_table("history_drafts",
        sa.Column("id", sa.Uuid(), primary_key=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("worker_id", sa.Uuid(), sa.ForeignKey("workers.id", ondelete="RESTRICT"), nullable=False),
        sa.Column("job_id", sa.Uuid(), sa.ForeignKey("jobs.id", ondelete="RESTRICT")),
        sa.Column("operation_id", sa.Uuid(), nullable=False), sa.Column("payload_hash", sa.String(64), nullable=False),
        sa.Column("language", sa.String(2), nullable=False), sa.Column("status", sa.String(20), nullable=False),
        sa.Column("audio_path", sa.String(500)), sa.Column("transcript", sa.Text()), sa.Column("details", sa.JSON()),
        sa.Column("model_metadata", sa.JSON(), nullable=False), sa.Column("error_code", sa.String(80)),
        sa.Column("lease_until", sa.DateTime(timezone=True)), sa.Column("attempts", sa.Integer(), nullable=False),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("claim_id", sa.Uuid(), sa.ForeignKey("history_claims.id", ondelete="RESTRICT")),
        sa.UniqueConstraint("worker_id", "operation_id"))
    op.create_index("ix_history_drafts_worker_id", "history_drafts", ["worker_id"])
    op.create_index("ix_history_drafts_status", "history_drafts", ["status"])


def downgrade():
    op.drop_table("history_drafts")
