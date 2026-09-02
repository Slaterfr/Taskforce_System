"""create activity_types and rank_quotas tables

Revision ID: 7143ef3e6653
Revises: 
Create Date: 2026-09-02 16:29:50.382624

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
import sqlmodel

# revision identifiers, used by Alembic.
revision: str = '7143ef3e6653'
down_revision: Union[str, Sequence[str], None] = None
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    op.create_table(
        'activity_types',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('tenant_id', sa.Integer(), nullable=False, server_default='1'),
        sa.Column('name', sqlmodel.sql.sqltypes.AutoString(length=100), nullable=False),
        sa.Column('points', sa.Float(), nullable=False, server_default='1.0'),
        sa.Column('is_limited', sa.Boolean(), nullable=False, server_default=sa.text('false')),
        sa.Column('description', sqlmodel.sql.sqltypes.AutoString(length=255), nullable=True),
        sa.Column('is_active', sa.Boolean(), nullable=False, server_default=sa.text('true')),
        sa.Column('created_at', sa.DateTime(), nullable=False, server_default=sa.func.now()),
        sa.PrimaryKeyConstraint('id')
    )
    op.create_index(op.f('ix_activity_types_name'), 'activity_types', ['name'], unique=False)
    op.create_index(op.f('ix_activity_types_tenant_id'), 'activity_types', ['tenant_id'], unique=False)

    op.create_table(
        'rank_quotas',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('tenant_id', sa.Integer(), nullable=False, server_default='1'),
        sa.Column('rank_name', sqlmodel.sql.sqltypes.AutoString(length=100), nullable=False),
        sa.Column('required_points', sa.Float(), nullable=False, server_default='0.0'),
        sa.Column('created_at', sa.DateTime(), nullable=False, server_default=sa.func.now()),
        sa.Column('updated_at', sa.DateTime(), nullable=False, server_default=sa.func.now()),
        sa.PrimaryKeyConstraint('id')
    )
    op.create_index(op.f('ix_rank_quotas_rank_name'), 'rank_quotas', ['rank_name'], unique=False)
    op.create_index(op.f('ix_rank_quotas_tenant_id'), 'rank_quotas', ['tenant_id'], unique=False)


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_index(op.f('ix_rank_quotas_tenant_id'), table_name='rank_quotas')
    op.drop_index(op.f('ix_rank_quotas_rank_name'), table_name='rank_quotas')
    op.drop_table('rank_quotas')
    op.drop_index(op.f('ix_activity_types_tenant_id'), table_name='activity_types')
    op.drop_index(op.f('ix_activity_types_name'), table_name='activity_types')
    op.drop_table('activity_types')
