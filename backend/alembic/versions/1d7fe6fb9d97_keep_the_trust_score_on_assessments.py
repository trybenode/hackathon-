"""keep the trust score on assessments

Revision ID: 1d7fe6fb9d97
Revises: 6c4e91a2d7f0
Create Date: 2026-10-08 01:05:42.566816
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = '1d7fe6fb9d97'
down_revision: Union[str, Sequence[str], None] = '6c4e91a2d7f0'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Nullable: assessments that stopped early have no score, and ones stored
    # before this column are filled in the next time they are reused.
    op.add_column("trust_assessments", sa.Column("score", sa.Numeric(5, 4), nullable=True))
    op.create_check_constraint(
        op.f("ck_trust_assessments_score_range"),
        "trust_assessments",
        "score IS NULL OR (score >= 0 AND score <= 1)",
    )


def downgrade() -> None:
    op.drop_constraint(
        op.f("ck_trust_assessments_score_range"), "trust_assessments", type_="check"
    )
    op.drop_column("trust_assessments", "score")
