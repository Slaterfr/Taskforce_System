"""create_multitenant_tables_and_columns

Revision ID: 87f5d3f5ccda
Revises: 7143ef3e6653
Create Date: 2026-09-20 14:04:27.435658

"""
from typing import Sequence, Union
import json
from datetime import datetime

from alembic import op
import sqlalchemy as sa
import sqlmodel
from config import settings


# revision identifiers, used by Alembic.
revision: str = '87f5d3f5ccda'
down_revision: Union[str, Sequence[str], None] = '7143ef3e6653'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

# Existing domain tables that need tenant_id added
DOMAIN_TABLES = [
    'members',
    'activity_logs',
    'promotion_logs',
    'rank_mappings',
    'member_stats',
    'missions',
    'mission_completions',
    'monthly_stats',
    'ac_periods',
    'activity_entries',
    'monthly_activity_entries',
    'inactivity_notices',
    'ac_exemptions',
    'period_statistics',
]


def upgrade() -> None:
    """Upgrade schema to multi-tenant structure."""
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    existing_tables = set(inspector.get_table_names())

    # 1. Create users table
    if 'users' not in existing_tables:
        op.create_table(
            'users',
            sa.Column('id', sa.Integer(), nullable=False),
            sa.Column('roblox_id', sa.String(length=50), nullable=False),
            sa.Column('roblox_username', sa.String(length=100), nullable=False),
            sa.Column('display_name', sa.String(length=100), nullable=True),
            sa.Column('avatar_url', sa.String(length=500), nullable=True),
            sa.Column('is_superadmin', sa.Boolean(), nullable=False, server_default=sa.text('false')),
            sa.Column('created_at', sa.DateTime(), nullable=False, server_default=sa.func.now()),
            sa.Column('last_login', sa.DateTime(), nullable=False, server_default=sa.func.now()),
            sa.PrimaryKeyConstraint('id')
        )
        op.create_index(op.f('ix_users_roblox_id'), 'users', ['roblox_id'], unique=True)
        op.create_index(op.f('ix_users_roblox_username'), 'users', ['roblox_username'], unique=False)

    # 2. Create groups table (tenants)
    if 'groups' not in existing_tables:
        op.create_table(
            'groups',
            sa.Column('id', sa.Integer(), nullable=False),
            sa.Column('roblox_group_id', sa.String(length=50), nullable=False),
            sa.Column('name', sa.String(length=150), nullable=False),
            sa.Column('description', sa.String(length=500), nullable=True),
            sa.Column('icon_url', sa.String(length=500), nullable=True),
            sa.Column('owner_user_id', sa.Integer(), nullable=True),
            sa.Column('is_active', sa.Boolean(), nullable=False, server_default=sa.text('true')),
            sa.Column('created_at', sa.DateTime(), nullable=False, server_default=sa.func.now()),
            sa.Column('settings', sa.JSON(), nullable=True),
            sa.ForeignKeyConstraint(['owner_user_id'], ['users.id'], ),
            sa.PrimaryKeyConstraint('id')
        )
        op.create_index(op.f('ix_groups_roblox_group_id'), 'groups', ['roblox_group_id'], unique=True)

    # 3. Create group_members table
    if 'group_members' not in existing_tables:
        op.create_table(
            'group_members',
            sa.Column('id', sa.Integer(), nullable=False),
            sa.Column('group_id', sa.Integer(), nullable=False),
            sa.Column('user_id', sa.Integer(), nullable=False),
            sa.Column('roblox_role_id', sa.Integer(), nullable=False, server_default='0'),
            sa.Column('roblox_role_name', sa.String(length=100), nullable=False, server_default='Guest'),
            sa.Column('roblox_rank', sa.Integer(), nullable=False, server_default='1'),
            sa.Column('system_role', sa.String(length=50), nullable=False, server_default='member'),
            sa.Column('joined_at', sa.DateTime(), nullable=False, server_default=sa.func.now()),
            sa.Column('last_synced', sa.DateTime(), nullable=False, server_default=sa.func.now()),
            sa.ForeignKeyConstraint(['group_id'], ['groups.id'], ),
            sa.ForeignKeyConstraint(['user_id'], ['users.id'], ),
            sa.PrimaryKeyConstraint('id')
        )
        op.create_index(op.f('ix_group_members_group_id'), 'group_members', ['group_id'], unique=False)
        op.create_index(op.f('ix_group_members_user_id'), 'group_members', ['user_id'], unique=False)

    # 4. Create group_permission_rules table
    if 'group_permission_rules' not in existing_tables:
        op.create_table(
            'group_permission_rules',
            sa.Column('id', sa.Integer(), nullable=False),
            sa.Column('group_id', sa.Integer(), nullable=False),
            sa.Column('min_roblox_rank', sa.Integer(), nullable=False, server_default='1'),
            sa.Column('max_roblox_rank', sa.Integer(), nullable=True),
            sa.Column('specific_role_id', sa.Integer(), nullable=True),
            sa.Column('system_role', sa.String(length=50), nullable=False),
            sa.Column('permissions', sa.JSON(), nullable=True),
            sa.ForeignKeyConstraint(['group_id'], ['groups.id'], ),
            sa.PrimaryKeyConstraint('id')
        )
        op.create_index(op.f('ix_group_permission_rules_group_id'), 'group_permission_rules', ['group_id'], unique=False)

    # 5. Seed default Taskforce group (id=1)
    roblox_gid = str(settings.ROBLOX_GROUP_ID or "1")
    group_table = sa.table(
        'groups',
        sa.column('id', sa.Integer),
        sa.column('roblox_group_id', sa.String),
        sa.column('name', sa.String),
        sa.column('is_active', sa.Boolean),
        sa.column('created_at', sa.DateTime),
        sa.column('settings', sa.JSON)
    )
    # Check if group 1 already exists
    existing_group = bind.execute(sa.text("SELECT id FROM groups WHERE id = 1")).fetchone()
    if not existing_group:
        op.bulk_insert(group_table, [
            {
                'id': 1,
                'roblox_group_id': roblox_gid,
                'name': 'Taskforce',
                'is_active': True,
                'created_at': datetime.utcnow(),
                'settings': json.dumps({'sync_enabled': True})
            }
        ])

    # 6. Add tenant_id to domain tables using batch mode
    for tbl_name in DOMAIN_TABLES:
        if tbl_name in existing_tables:
            columns = [c['name'] for c in inspector.get_columns(tbl_name)]
            if 'tenant_id' not in columns:
                with op.batch_alter_table(tbl_name) as batch_op:
                    batch_op.add_column(sa.Column('tenant_id', sa.Integer(), nullable=False, server_default='1'))
                    batch_op.create_index(f'ix_{tbl_name}_tenant_id', ['tenant_id'], unique=False)


def downgrade() -> None:
    """Downgrade schema."""
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    existing_tables = set(inspector.get_table_names())

    for tbl_name in DOMAIN_TABLES:
        if tbl_name in existing_tables:
            columns = [c['name'] for c in inspector.get_columns(tbl_name)]
            if 'tenant_id' in columns:
                with op.batch_alter_table(tbl_name) as batch_op:
                    batch_op.drop_index(f'ix_{tbl_name}_tenant_id')
                    batch_op.drop_column('tenant_id')

    if 'group_permission_rules' in existing_tables:
        op.drop_index(op.f('ix_group_permission_rules_group_id'), table_name='group_permission_rules')
        op.drop_table('group_permission_rules')

    if 'group_members' in existing_tables:
        op.drop_index(op.f('ix_group_members_user_id'), table_name='group_members')
        op.drop_index(op.f('ix_group_members_group_id'), table_name='group_members')
        op.drop_table('group_members')

    if 'groups' in existing_tables:
        op.drop_index(op.f('ix_groups_roblox_group_id'), table_name='groups')
        op.drop_table('groups')

    if 'users' in existing_tables:
        op.drop_index(op.f('ix_users_roblox_username'), table_name='users')
        op.drop_index(op.f('ix_users_roblox_id'), table_name='users')
        op.drop_table('users')
