"""Private clarification originals and derivative translations."""
import sqlalchemy as sa
from alembic import op
revision = "a83c2d43e9f2"
down_revision = "a82c2d43e9f1"
branch_labels = None
depends_on = None


def base_columns():
    return [sa.Column("id", sa.Uuid(), primary_key=True), sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False), sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False)]


def upgrade():
    op.create_table("history_messages", *base_columns(),
        sa.Column("request_id", sa.Uuid(), sa.ForeignKey("history_confirmation_requests.id", ondelete="RESTRICT"), nullable=False),
        sa.Column("actor_role", sa.String(10), nullable=False), sa.Column("actor_id", sa.Uuid(), sa.ForeignKey("users.id", ondelete="RESTRICT")),
        sa.Column("operation_id", sa.Uuid(), nullable=False), sa.Column("payload_hash", sa.String(64), nullable=False),
        sa.Column("language", sa.String(2), nullable=False), sa.Column("text", sa.Text(), nullable=False),
        sa.UniqueConstraint("request_id", "actor_role", "operation_id"))
    op.create_index("ix_history_messages_request_id", "history_messages", ["request_id"])
    op.create_table("history_message_translations", *base_columns(),
        sa.Column("message_id", sa.Uuid(), sa.ForeignKey("history_messages.id", ondelete="RESTRICT"), nullable=False),
        sa.Column("target", sa.String(2), nullable=False), sa.Column("status", sa.String(20), nullable=False),
        sa.Column("text", sa.Text()), sa.Column("model", sa.String(80), nullable=False), sa.Column("model_revision", sa.String(160)), sa.Column("error_code", sa.String(80)),
        sa.UniqueConstraint("message_id", "target"))


def downgrade():
    op.drop_table("history_message_translations")
    op.drop_table("history_messages")
