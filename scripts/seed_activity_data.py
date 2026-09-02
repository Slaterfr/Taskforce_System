"""
Seed initial activity types and rank quotas from ac_constants.py.
Idempotent: updates existing records or inserts new ones.
"""
import sys
import os

BASE_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
if BASE_DIR not in sys.path:
    sys.path.insert(0, BASE_DIR)

from sqlmodel import select
from database.engine import engine, Session
from database.ac_models import ActivityType, RankQuota
from database.ac_constants import ACTIVITY_TYPES, AC_QUOTAS

DEFAULT_TENANT_ID = 1


def seed():
    print(f"[*] Seeding ActivityTypes and RankQuotas for tenant_id={DEFAULT_TENANT_ID}...")
    with Session(engine) as session:
        # Seed Activity Types
        for name, data in ACTIVITY_TYPES.items():
            existing = session.exec(
                select(ActivityType).where(
                    ActivityType.tenant_id == DEFAULT_TENANT_ID,
                    ActivityType.name == name,
                )
            ).first()

            if existing:
                existing.points = data["points"]
                existing.is_limited = data.get("limited", False)
                existing.description = data.get("description", "")
                existing.is_active = True
                print(f"  [ActivityType] Updated: {name} ({existing.points} pts)")
            else:
                new_act = ActivityType(
                    tenant_id=DEFAULT_TENANT_ID,
                    name=name,
                    points=data["points"],
                    is_limited=data.get("limited", False),
                    description=data.get("description", ""),
                    is_active=True,
                )
                session.add(new_act)
                print(f"  [ActivityType] Added: {name} ({data['points']} pts)")

        # Seed Rank Quotas
        for rank_name, required_pts in AC_QUOTAS.items():
            existing_quota = session.exec(
                select(RankQuota).where(
                    RankQuota.tenant_id == DEFAULT_TENANT_ID,
                    RankQuota.rank_name == rank_name,
                )
            ).first()

            if existing_quota:
                existing_quota.required_points = required_pts
                print(f"  [RankQuota] Updated: {rank_name} -> {required_pts} pts")
            else:
                new_quota = RankQuota(
                    tenant_id=DEFAULT_TENANT_ID,
                    rank_name=rank_name,
                    required_points=required_pts,
                )
                session.add(new_quota)
                print(f"  [RankQuota] Added: {rank_name} -> {required_pts} pts")

        session.commit()
    print("[+] Seeding completed successfully!")


if __name__ == "__main__":
    seed()
