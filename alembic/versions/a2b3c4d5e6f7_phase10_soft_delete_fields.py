"""phase10_soft_delete_fields

Add deleted_at / deleted_by to devices, racks, switches, work_orders.
Connection already has these fields (added in initial schema).

Revision ID: a2b3c4d5e6f7
Revises: e1ca85dda023
Create Date: 2026-05-18

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = 'a2b3c4d5e6f7'
down_revision: Union[str, Sequence[str], None] = 'e1ca85dda023'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # deleted_by is a logical FK to users.id; SQLite doesn't enforce unnamed FKs in batch mode,
    # so we add as plain Integer and let SQLAlchemy handle the relationship.
    for table in ('devices', 'racks', 'switches', 'work_orders'):
        with op.batch_alter_table(table, schema=None) as batch_op:
            batch_op.add_column(sa.Column('deleted_at', sa.DateTime(), nullable=True))
            batch_op.add_column(sa.Column('deleted_by', sa.Integer(), nullable=True))


def downgrade() -> None:
    with op.batch_alter_table('work_orders', schema=None) as batch_op:
        batch_op.drop_column('deleted_by')
        batch_op.drop_column('deleted_at')

    with op.batch_alter_table('switches', schema=None) as batch_op:
        batch_op.drop_column('deleted_by')
        batch_op.drop_column('deleted_at')

    with op.batch_alter_table('racks', schema=None) as batch_op:
        batch_op.drop_column('deleted_by')
        batch_op.drop_column('deleted_at')

    with op.batch_alter_table('devices', schema=None) as batch_op:
        batch_op.drop_column('deleted_by')
        batch_op.drop_column('deleted_at')
