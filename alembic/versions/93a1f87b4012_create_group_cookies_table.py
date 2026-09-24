"""create group_cookies table

Revision ID: 93a1f87b4012
Revises: 87f5d3f5ccda
Create Date: 2026-09-20 16:47:00.000000

"""
from typing import Sequence, Union
from datetime import datetime
from alembic import op
import sqlalchemy as sa
from config import settings


# revision identifiers, used by Alembic.
revision: str = '93a1f87b4012'
down_revision: Union[str, Sequence[str], None] = '87f5d3f5ccda'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    existing_tables = set(inspector.get_table_names())

    if 'group_cookies' not in existing_tables:
        op.create_table(
            'group_cookies',
            sa.Column('id', sa.Integer(), nullable=False),
            sa.Column('group_id', sa.Integer(), nullable=False),
            sa.Column('cookie', sa.Text(), nullable=False),
            sa.Column('bot_username', sa.String(length=100), nullable=True),
            sa.Column('bot_id', sa.String(length=50), nullable=True),
            sa.Column('is_valid', sa.Boolean(), nullable=False, server_default=sa.text('true')),
            sa.Column('last_validated', sa.DateTime(), nullable=True),
            sa.Column('created_at', sa.DateTime(), nullable=False, server_default=sa.func.now()),
            sa.Column('updated_at', sa.DateTime(), nullable=False, server_default=sa.func.now()),
            sa.ForeignKeyConstraint(['group_id'], ['groups.id'], ondelete='CASCADE'),
            sa.PrimaryKeyConstraint('id')
        )
        op.create_index(op.f('ix_group_cookies_group_id'), 'group_cookies', ['group_id'], unique=True)

        # Pre-seed Group 1 with existing ROBLOX_COOKIE if available
        roblox_cookie = getattr(settings, 'ROBLOX_COOKIE', None)
        if roblox_cookie:
            group_cookie_table = sa.table(
                'group_cookies',
                sa.column('group_id', sa.Integer),
                sa.column('cookie', sa.Text),
                sa.column('is_valid', sa.Boolean),
                sa.column('created_at', sa.DateTime),
                sa.column('updated_at', sa.DateTime),
            )
            op.bulk_insert(group_cookie_table, [
                {
                    'group_id': 1,
                    'cookie': roblox_cookie,
                    'is_valid': True,
                    'created_at': datetime.utcnow(),
                    'updated_at': datetime.utcnow(),
                }
            ])


def downgrade() -> None:
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    existing_tables = set(inspector.get_table_names())

    if 'group_cookies' in existing_tables:
        op.drop_index(op.f('ix_group_cookies_group_id'), table_name='group_cookies')
        op.drop_table('group_cookies')
