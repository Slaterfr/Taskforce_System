"""add group discord channel fields

Revision ID: b52e89d13456
Revises: a41f87c12b03
Create Date: 2026-10-29 14:40:00.000000

"""
from typing import Sequence, Union
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'b52e89d13456'
down_revision: Union[str, Sequence[str], None] = 'a41f87c12b03'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Add ranks_channel_id, activity_channel_id, and webhook_channel_id to groups table
    with op.batch_alter_table('groups') as batch_op:
        batch_op.add_column(sa.Column('ranks_channel_id', sa.String(length=50), nullable=True))
        batch_op.add_column(sa.Column('activity_channel_id', sa.String(length=50), nullable=True))
        batch_op.add_column(sa.Column('webhook_channel_id', sa.String(length=50), nullable=True))


def downgrade() -> None:
    with op.batch_alter_table('groups') as batch_op:
        batch_op.drop_column('webhook_channel_id')
        batch_op.drop_column('activity_channel_id')
        batch_op.drop_column('ranks_channel_id')
