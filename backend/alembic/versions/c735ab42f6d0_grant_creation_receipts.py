"""Add worker-scoped operation identifiers for lost grant responses."""
import sqlalchemy as sa
from alembic import op
revision = "c735ab42f6d0"
down_revision = "b6249c82e3a1"
branch_labels = None
depends_on = None


def upgrade() -> None:
    for table in ("share_grants", "platform_grants"):
        op.add_column(table, sa.Column("operation_id", sa.Uuid(), nullable=True))
        op.add_column(table, sa.Column("payload_hash", sa.String(64), nullable=True))
        op.create_unique_constraint(f"uq_{table}_worker_operation", table, ["worker_id", "operation_id"])


def downgrade() -> None:
    for table in ("share_grants", "platform_grants"):
        op.drop_constraint(f"uq_{table}_worker_operation", table, type_="unique")
        op.drop_column(table, "payload_hash")
        op.drop_column(table, "operation_id")
