"""rename_type_to_transaction_type

Revision ID: 3ff48f925b87
Revises: dea19723a996
Create Date: 2026-08-03 15:43:50.290743

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '3ff48f925b87'
down_revision: Union[str, None] = 'dea19723a996'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.alter_column('credit_transactions', 'type', new_column_name='transaction_type')


def downgrade() -> None:
    op.alter_column('credit_transactions', 'transaction_type', new_column_name='type')
