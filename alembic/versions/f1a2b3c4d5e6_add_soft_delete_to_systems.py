"""add_soft_delete_to_systems

Add deleted_at / deleted_by to systems, mirroring devices/racks/switches/work_orders
(a2b3c4d5e6f7). System previously always hard-deleted.

Revision ID: f1a2b3c4d5e6
Revises: e5f6a7b8c9d0
Create Date: 2026-09-03

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = 'f1a2b3c4d5e6'
down_revision: Union[str, Sequence[str], None] = 'e5f6a7b8c9d0'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    with op.batch_alter_table('systems', schema=None) as batch_op:
        batch_op.add_column(sa.Column('deleted_at', sa.DateTime(), nullable=True))
        batch_op.add_column(sa.Column('deleted_by', sa.Integer(), nullable=True))


def downgrade() -> None:
    with op.batch_alter_table('systems', schema=None) as batch_op:
        batch_op.drop_column('deleted_by')
        batch_op.drop_column('deleted_at')
