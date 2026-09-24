from database.engine import engine
from sqlmodel import Session, select
from database.tenant_models import Group
from database.permission_models import RankPermission
from database.models import Member, ActivityLog
from database.ac_models import ActivityType, RankQuota

def main():
    with Session(engine) as s:
        groups = s.exec(select(Group)).all()
        print(f"Total Sectors / Tenants: {len(groups)}")
        for g in groups:
            perms = s.exec(select(RankPermission).where(RankPermission.tenant_id == g.id)).all()
            members = s.exec(select(Member).where(Member.tenant_id == g.id)).all()
            acts = s.exec(select(ActivityLog).where(ActivityLog.tenant_id == g.id)).all()
            types = s.exec(select(ActivityType).where(ActivityType.tenant_id == g.id)).all()
            quotas = s.exec(select(RankQuota).where(RankQuota.tenant_id == g.id)).all()
            st = g.get_settings_dict()
            print(f"\n--- Sector #{g.id}: {g.name} ---")
            print(f"  Roblox Group ID: {g.roblox_group_id}")
            print(f"  Discord Group ID: {g.discord_group_id}")
            print(f"  Theme: {st.get('theme', 'tactical-dark')}")
            print(f"  Crest URL: {st.get('crest_url', 'Default')}")
            print(f"  Members Roster: {len(members)}")
            print(f"  Activity Logs: {len(acts)}")
            print(f"  Activity Types: {len(types)}")
            print(f"  Rank Quotas: {len(quotas)}")
            print(f"  Rank Permissions Matrix: {len(perms)} roles configured")

if __name__ == "__main__":
    main()
