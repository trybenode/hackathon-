"""Durable private translated audio, served only through authorized thread routes."""
import sqlalchemy as sa
from alembic import op
revision = "a85c2d43e9f4"
down_revision = "a84c2d43e9f3"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table("history_message_audio",
        sa.Column("id", sa.Uuid(), primary_key=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("translation_id", sa.Uuid(), sa.ForeignKey("history_message_translations.id", ondelete="RESTRICT"), nullable=False),
        sa.Column("fingerprint", sa.String(64), nullable=False), sa.Column("language", sa.String(2), nullable=False),
        sa.Column("status", sa.String(20), nullable=False), sa.Column("provider_model", sa.String(160), nullable=False), sa.Column("provider_version", sa.String(160), nullable=False),
        sa.Column("audio_path", sa.String(500)), sa.Column("error_code", sa.String(80)),
        sa.Column("attempts", sa.Integer(), nullable=False), sa.Column("lease_until", sa.DateTime(timezone=True)),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=False),
        sa.UniqueConstraint("translation_id", "fingerprint", name="uq_history_audio_translation_fingerprint"))
    op.create_index("ix_history_message_audio_status", "history_message_audio", ["status"])


def downgrade() -> None:
    op.drop_table("history_message_audio")
