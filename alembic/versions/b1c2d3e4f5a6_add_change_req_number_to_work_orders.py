"""add_change_req_number_to_work_orders

Revision ID: b1c2d3e4f5a6
Revises: a2b3c4d5e6f7
Create Date: 2026-05-19

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = 'b1c2d3e4f5a6'
down_revision: Union[str, Sequence[str], None] = 'a2b3c4d5e6f7'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    with op.batch_alter_table('work_orders', schema=None) as batch_op:
        batch_op.add_column(sa.Column('change_req_number', sa.String(64), nullable=True))


def downgrade() -> None:
    with op.batch_alter_table('work_orders', schema=None) as batch_op:
        batch_op.drop_column('change_req_number')
