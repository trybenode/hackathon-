"""guarantee owner platform

Revision ID: 79938cf43af0
Revises: 7f07ae1bd32a
Create Date: 2026-10-10 19:39:30.343381
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = '79938cf43af0'
down_revision: Union[str, Sequence[str], None] = '7f07ae1bd32a'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Guarantees made before platforms were tracked have no owner.
    op.add_column('guarantor_agreements', sa.Column('organization_id', sa.Uuid(), nullable=True))
    op.create_foreign_key(op.f('fk_guarantor_agreements_organization_id_organizations'), 'guarantor_agreements', 'organizations', ['organization_id'], ['id'], ondelete='SET NULL')


def downgrade() -> None:
    op.drop_constraint(op.f('fk_guarantor_agreements_organization_id_organizations'), 'guarantor_agreements', type_='foreignkey')
    op.drop_column('guarantor_agreements', 'organization_id')
