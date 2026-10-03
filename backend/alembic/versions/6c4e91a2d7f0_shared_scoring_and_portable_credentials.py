"""shared scoring and portable credentials

Revision ID: 6c4e91a2d7f0
Revises: a27e91b4c6d5
Create Date: 2026-10-03 09:14:10.468091
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa



revision: str = '6c4e91a2d7f0'
down_revision: Union[str, Sequence[str], None] = 'a27e91b4c6d5'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column(
        "normalized_outcomes",
        sa.Column("cancelled_by", sa.String(length=20), nullable=True),
    )
    op.add_column(
        "normalized_outcomes",
        sa.Column("dispute_resolution", sa.String(length=20), nullable=True),
    )
    op.add_column(
        "normalized_outcomes",
        sa.Column("client_id", sa.String(length=255), nullable=True),
    )
    op.add_column(
        "normalized_outcomes",
        sa.Column("source_platform", sa.String(length=120), server_default="legacy", nullable=False),
    )
    op.add_column(
        "normalized_outcomes",
        sa.Column("import_method", sa.String(length=20), server_default="native", nullable=False),
    )
    op.add_column(
        "normalized_outcomes",
        sa.Column("verified", sa.Boolean(), server_default=sa.false(), nullable=False),
    )
    op.create_check_constraint(
        op.f("ck_normalized_outcomes_cancelled_by_valid"),
        "normalized_outcomes",
        "cancelled_by IS NULL OR cancelled_by IN ('worker', 'client', 'platform')",
    )
    op.create_check_constraint(
        op.f("ck_normalized_outcomes_dispute_resolution_valid"),
        "normalized_outcomes",
        "dispute_resolution IS NULL OR dispute_resolution IN ('open', 'upheld', 'dismissed')",
    )
    op.create_check_constraint(
        op.f("ck_normalized_outcomes_import_method_valid"),
        "normalized_outcomes",
        "import_method IN ('native', 'api', 'csv_upload')",
    )

    op.add_column(
        "trust_assessments",
        sa.Column("band", sa.String(length=24), server_default="Building History", nullable=False),
    )
    op.add_column(
        "trust_assessments",
        sa.Column("signals_used", sa.JSON(), server_default="[]", nullable=False),
    )
    op.add_column(
        "trust_assessments",
        sa.Column("explanation_summary", sa.Text(), server_default="", nullable=False),
    )

    op.add_column(
        "credential_transfers",
        sa.Column("worker_id", sa.Uuid(), nullable=True),
    )
    op.execute(
        "UPDATE credential_transfers AS transfer "
        "SET worker_id = credential.worker_id "
        "FROM credentials AS credential "
        "WHERE transfer.credential_id = credential.id"
    )
    op.alter_column("credential_transfers", "worker_id", nullable=False)
    op.create_foreign_key(
        op.f("fk_credential_transfers_worker_id_workers"),
        "credential_transfers",
        "workers",
        ["worker_id"],
        ["id"],
        ondelete="CASCADE",
    )
    op.create_unique_constraint(
        op.f("uq_credential_transfers_worker_id"),
        "credential_transfers",
        ["worker_id", "direction", "transfer_token_hash"],
    )


def downgrade() -> None:
    op.drop_constraint(op.f("uq_credential_transfers_worker_id"), "credential_transfers", type_="unique")
    op.drop_constraint(
        op.f("fk_credential_transfers_worker_id_workers"), "credential_transfers", type_="foreignkey"
    )
    op.drop_column("credential_transfers", "worker_id")

    op.drop_column("trust_assessments", "explanation_summary")
    op.drop_column("trust_assessments", "signals_used")
    op.drop_column("trust_assessments", "band")

    op.drop_constraint(
        op.f("ck_normalized_outcomes_import_method_valid"), "normalized_outcomes", type_="check"
    )
    op.drop_constraint(
        op.f("ck_normalized_outcomes_dispute_resolution_valid"), "normalized_outcomes", type_="check"
    )
    op.drop_constraint(
        op.f("ck_normalized_outcomes_cancelled_by_valid"), "normalized_outcomes", type_="check"
    )
    op.drop_column("normalized_outcomes", "verified")
    op.drop_column("normalized_outcomes", "import_method")
    op.drop_column("normalized_outcomes", "source_platform")
    op.drop_column("normalized_outcomes", "client_id")
    op.drop_column("normalized_outcomes", "dispute_resolution")
    op.drop_column("normalized_outcomes", "cancelled_by")
