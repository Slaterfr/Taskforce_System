"""drop legacy single-tenant unique constraints

Revision ID: a41f87c12b03
Revises: 93a1f87b4012
Create Date: 2026-09-20 17:15:00.000000

"""
from typing import Sequence, Union
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'a41f87c12b03'
down_revision: Union[str, Sequence[str], None] = '93a1f87b4012'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # 1. rank_mappings: drop global system_rank uniqueness, add tenant-scoped uniqueness
    op.execute("ALTER TABLE rank_mappings DROP CONSTRAINT IF EXISTS rank_mappings_system_rank_key;")
    op.execute("ALTER TABLE rank_mappings ALTER COLUMN roblox_role_id TYPE BIGINT;")
    op.execute("ALTER TABLE rank_mappings DROP CONSTRAINT IF EXISTS uq_rank_mappings_tenant_role_id;")
    op.execute("ALTER TABLE rank_mappings ADD CONSTRAINT uq_rank_mappings_tenant_role_id UNIQUE (tenant_id, roblox_role_id);")

    # 2. members: drop global discord uniqueness, allow members across multiple tenants
    op.execute("ALTER TABLE members DROP CONSTRAINT IF EXISTS members_discord_username_key;")
    op.execute("ALTER TABLE members DROP CONSTRAINT IF EXISTS members_discord_id_key;")

    # 3. group_permission_rules & group_members: ensure role IDs are BIGINT
    op.execute("ALTER TABLE group_permission_rules ALTER COLUMN specific_role_id TYPE BIGINT;")
    op.execute("ALTER TABLE group_members ALTER COLUMN roblox_role_id TYPE BIGINT;")


def downgrade() -> None:
    op.execute("ALTER TABLE rank_mappings DROP CONSTRAINT IF EXISTS uq_rank_mappings_tenant_role_id;")
    op.execute("ALTER TABLE rank_mappings ADD CONSTRAINT rank_mappings_system_rank_key UNIQUE (system_rank);")
