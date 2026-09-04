"""patch_panel_lifecycle_occupancy_trunks

Schema for the "Patch panel lifecycle, port occupancy, and trunk modeling"
design (DESIGN_DECISIONS.md, 2026-09-03). Implements schema for scope (b)+(c)
in one pass so the dev DB only needs recreating once; occupancy logic,
uniqueness enforcement, trunk discovery, and UI land in later sessions.

- patch_panels: add deleted_at / deleted_by, matching devices/racks/switches/
  work_orders/systems.
- patch_port_flags: sparse table for manually-flagged (red/broken) ports.
  One row per currently-flagged panel+port; clearing a flag deletes the row.
- trunks: panel-to-panel structured cabling, lazily populated by connection
  discovery (not built here — table starts empty, no backfill).

SQLite/Alembic batch mode requires every constraint to be explicitly named
(unnamed constraints raise "Constraint must have a name" when the table is
recreated) — every FK below is named accordingly, including deleted_by on
patch_panels via a separate create_foreign_key call in the same batch block,
since add_column() cannot carry an inline FK in batch mode.

Revision ID: a7b8c9d0e1f2
Revises: f1a2b3c4d5e6
Create Date: 2026-09-04

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = 'a7b8c9d0e1f2'
down_revision: Union[str, Sequence[str], None] = 'f1a2b3c4d5e6'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    with op.batch_alter_table('patch_panels', schema=None) as batch_op:
        batch_op.add_column(sa.Column('deleted_at', sa.DateTime(), nullable=True))
        batch_op.add_column(sa.Column('deleted_by', sa.Integer(), nullable=True))
        batch_op.create_foreign_key(
            'fk_patch_panels_deleted_by', 'users', ['deleted_by'], ['id']
        )

    op.create_table(
        'patch_port_flags',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('panel_id', sa.Integer(), nullable=False),
        sa.Column('port', sa.String(32), nullable=False),
        sa.Column('created_at', sa.DateTime(), server_default=sa.func.now(), nullable=False),
        sa.Column('set_by', sa.Integer(), nullable=True),
        sa.Column('note', sa.Text(), nullable=True),
        sa.ForeignKeyConstraint(['panel_id'], ['patch_panels.id'],
                                 name='fk_patch_port_flags_panel_id'),
        sa.ForeignKeyConstraint(['set_by'], ['users.id'],
                                 name='fk_patch_port_flags_set_by'),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('panel_id', 'port', name='uq_patch_port_flag_panel_port'),
    )
    op.create_index(
        'ix_patch_port_flags_panel_port', 'patch_port_flags', ['panel_id', 'port']
    )

    op.create_table(
        'trunks',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('panel_a_id', sa.Integer(), nullable=False),
        sa.Column('port_a', sa.String(32), nullable=False),
        sa.Column('panel_b_id', sa.Integer(), nullable=False),
        sa.Column('port_b', sa.String(32), nullable=False),
        sa.Column('discovered_via_connection_id', sa.Integer(), nullable=True),
        sa.Column('created_at', sa.DateTime(), server_default=sa.func.now(), nullable=False),
        sa.ForeignKeyConstraint(['panel_a_id'], ['patch_panels.id'],
                                 name='fk_trunks_panel_a_id'),
        sa.ForeignKeyConstraint(['panel_b_id'], ['patch_panels.id'],
                                 name='fk_trunks_panel_b_id'),
        sa.ForeignKeyConstraint(['discovered_via_connection_id'], ['connections.id'],
                                 name='fk_trunks_discovered_via_connection_id'),
        sa.PrimaryKeyConstraint('id'),
    )
    op.create_index('ix_trunks_panel_a', 'trunks', ['panel_a_id', 'port_a'])
    op.create_index('ix_trunks_panel_b', 'trunks', ['panel_b_id', 'port_b'])


def downgrade() -> None:
    op.drop_index('ix_trunks_panel_b', table_name='trunks')
    op.drop_index('ix_trunks_panel_a', table_name='trunks')
    op.drop_table('trunks')

    op.drop_index('ix_patch_port_flags_panel_port', table_name='patch_port_flags')
    op.drop_table('patch_port_flags')

    with op.batch_alter_table('patch_panels', schema=None) as batch_op:
        batch_op.drop_constraint('fk_patch_panels_deleted_by', type_='foreignkey')
        batch_op.drop_column('deleted_by')
        batch_op.drop_column('deleted_at')
