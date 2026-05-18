"""add_port_count_to_device_types

slot_count = blade slots for chassis devices
port_count = switchport capacity for switch device types
Both nullable. Most devices use one or neither.

Revision ID: e1ca85dda023
Revises: 3e19e0cddf47
Create Date: 2026-05-18

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = 'e1ca85dda023'
down_revision: Union[str, Sequence[str], None] = '3e19e0cddf47'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    with op.batch_alter_table('device_types', schema=None) as batch_op:
        batch_op.add_column(sa.Column('port_count', sa.Integer(), nullable=True))


def downgrade() -> None:
    with op.batch_alter_table('device_types', schema=None) as batch_op:
        batch_op.drop_column('port_count')
