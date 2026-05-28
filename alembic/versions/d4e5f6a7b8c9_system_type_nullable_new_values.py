"""system_type_nullable_new_values

Make systems.system_type nullable and migrate to new value set
(cluster, ha_pair, standalone). Old values (server/storage/appliance/other)
are cleared to NULL — type is now purely informational metadata.

Revision ID: d4e5f6a7b8c9
Revises: c3d4e5f6a7b8
Create Date: 2026-05-28

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = 'd4e5f6a7b8c9'
down_revision: Union[str, Sequence[str], None] = 'c3d4e5f6a7b8'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

_VALID = {'cluster', 'ha_pair', 'standalone'}


def upgrade() -> None:
    # Make nullable first (batch recreates the table), then clear old values.
    with op.batch_alter_table('systems', schema=None) as batch_op:
        batch_op.alter_column('system_type',
                              existing_type=sa.String(32),
                              nullable=True)
    op.execute(
        "UPDATE systems SET system_type = NULL "
        "WHERE system_type NOT IN ('cluster', 'ha_pair', 'standalone')"
    )


def downgrade() -> None:
    # Restore NOT NULL with a safe default; prior values are unrecoverable.
    op.execute("UPDATE systems SET system_type = 'server' WHERE system_type IS NULL")
    with op.batch_alter_table('systems', schema=None) as batch_op:
        batch_op.alter_column('system_type',
                              existing_type=sa.String(32),
                              nullable=False)
