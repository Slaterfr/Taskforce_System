import sys
import os
from datetime import datetime

# Set up path
sys.path.insert(0, os.path.abspath("."))

from database.engine import db_session
from database.models import Member
from database.tenant_models import Group
from database.ac_models import (
    ACPeriod,
    ActivityEntry,
    MonthlyActivityEntry,
    Title,
    ActivityType,
)
from services import ac_service
from utils.ac_reports import ACReportGenerator
from utils.tenant_context import set_tenant_context
from sqlmodel import select

def test_monthly_activity_title_flow():
    test_tenant_id = 999
    set_tenant_context(test_tenant_id)
    session = db_session()

    print("--- 1. Set up test tenant and period ---")
    # Clean up any leftover test data
    session.query(Title).filter_by(tenant_id=test_tenant_id).delete()
    session.query(ActivityEntry).filter_by(tenant_id=test_tenant_id).delete()
    session.query(MonthlyActivityEntry).filter_by(tenant_id=test_tenant_id).delete()
    session.query(ACPeriod).filter_by(tenant_id=test_tenant_id).delete()
    session.query(Member).filter_by(tenant_id=test_tenant_id).delete()
    session.commit()

    # Create test period
    period = ACPeriod(
        tenant_id=test_tenant_id,
        period_name="Test Cycle September 2026",
        start_date=datetime(2026, 9, 1),
        end_date=datetime(2026, 9, 15),
        is_active=True,
    )
    session.add(period)
    session.commit()
    session.refresh(period)

    # Create test members
    m1 = Member(
        tenant_id=test_tenant_id,
        roblox_id=99901,
        roblox_username="TestUserAlpha",
        discord_username="AlphaUser",
        current_rank="Officer",
        is_active=True,
    )
    m2 = Member(
        tenant_id=test_tenant_id,
        roblox_id=99902,
        roblox_username="TestUserBeta",
        discord_username="BetaUser",
        current_rank="Trooper",
        is_active=True,
    )
    session.add(m1)
    session.add(m2)
    session.commit()
    session.refresh(m1)
    session.refresh(m2)

    print("--- 2. Create custom titles for tenant ---")
    # Title 1: Monthly Title using Tryouts (requires 3)
    t1 = Title(
        tenant_id=test_tenant_id,
        name="Chief Recruiter",
        activity_required="Tryout",
        quantity_required=3,
        period_type="monthly",
        description="Top tryout host of the month",
        is_active=True,
    )
    # Title 2: Single Cycle Title using Events (Training + Raid + Patrol) (requires 2)
    t2 = Title(
        tenant_id=test_tenant_id,
        name="Field Commander",
        activity_required="Events (Training + Raid + Patrol)",
        quantity_required=2,
        period_type="cycle",
        description="Top event commander this cycle",
        is_active=True,
    )
    session.add(t1)
    session.add(t2)
    session.commit()

    print("--- 3. Log activities for members ---")
    # Alpha gets 4 tryouts and 1 training
    res1 = ac_service.log_activity(
        member_id=m1.id,
        activity_type="Tryout",
        period=period,
        quantity=4,
        logged_by="Admin",
    )
    print("res1:", res1)
    ac_service.log_activity(
        member_id=m1.id,
        activity_type="Training",
        period=period,
        quantity=1,
        logged_by="Admin",
    )

    # Beta gets 3 trainings (events)
    ac_service.log_activity(
        member_id=m2.id,
        activity_type="Training",
        period=period,
        quantity=3,
        logged_by="Admin",
    )

    # Verify both tables are populated
    cycle_entries = session.exec(select(ActivityEntry).where(ActivityEntry.ac_period_id == period.id)).all()
    monthly_entries = session.exec(select(MonthlyActivityEntry).where(MonthlyActivityEntry.ac_period_id == period.id)).all()
    print(f"Cycle ActivityEntry count: {len(cycle_entries)}")
    print(f"Persistent MonthlyActivityEntry count: {len(monthly_entries)}")
    assert len(cycle_entries) == 8, f"Expected 8 cycle entries, got {len(cycle_entries)}"
    assert len(monthly_entries) == 8, f"Expected 8 monthly entries, got {len(monthly_entries)}"

    print("--- 4. Verify title rewards calculation with custom titles ---")
    rewards = ac_service.calculate_title_rewards(cycle_entries, period)
    print("Calculated Rewards:", rewards)

    assert "Chief Recruiter" in rewards
    assert rewards["Chief Recruiter"]["winner"] == "AlphaUser"
    assert rewards["Chief Recruiter"]["count"] == 4
    assert rewards["Chief Recruiter"]["qualified"] is True
    assert rewards["Chief Recruiter"]["is_monthly"] is True

    assert "Field Commander" in rewards
    assert rewards["Field Commander"]["winner"] == "BetaUser"
    assert rewards["Field Commander"]["count"] == 3
    assert rewards["Field Commander"]["qualified"] is True
    assert rewards["Field Commander"]["is_monthly"] is False

    print("--- 5. Test Persistence: Delete/Clear cycle activities ---")
    deleted = ac_service.clear_all_activities(period.id)
    print(f"Cleared {deleted} cycle activities.")

    cycle_entries_after = session.exec(select(ActivityEntry).where(ActivityEntry.ac_period_id == period.id)).all()
    monthly_entries_after = session.exec(select(MonthlyActivityEntry).where(MonthlyActivityEntry.ac_period_id == period.id)).all()
    print(f"Cycle ActivityEntry count after clear: {len(cycle_entries_after)}")
    print(f"Persistent MonthlyActivityEntry count after clear: {len(monthly_entries_after)}")
    assert len(cycle_entries_after) == 0, "Cycle entries should be cleared"
    assert len(monthly_entries_after) == 8, "Monthly entries must remain completely intact!"

    print("--- 6. Recalculate title rewards after cycle clear ---")
    rewards_after_clear = ac_service.calculate_title_rewards([], period)
    print("Calculated Rewards After Clear:", rewards_after_clear)

    # Monthly title Chief Recruiter MUST still be intact with 4 entries and AlphaUser winning!
    assert "Chief Recruiter" in rewards_after_clear
    assert rewards_after_clear["Chief Recruiter"]["winner"] == "AlphaUser"
    assert rewards_after_clear["Chief Recruiter"]["count"] == 4
    assert rewards_after_clear["Chief Recruiter"]["qualified"] is True

    # Single cycle title also falls back to monthly activity replica for that period
    assert "Field Commander" in rewards_after_clear
    assert rewards_after_clear["Field Commander"]["winner"] == "BetaUser"
    assert rewards_after_clear["Field Commander"]["count"] == 3

    print("--- 7. Test ACReportGenerator title calculation ---")
    report_gen = ACReportGenerator(period, members_progress=[])
    report_rewards = report_gen.calculate_title_rewards()
    print("Report Generator Rewards:", report_rewards)

    print("--- 8. Cleanup test data ---")
    session.query(Title).filter_by(tenant_id=test_tenant_id).delete()
    session.query(ActivityEntry).filter_by(tenant_id=test_tenant_id).delete()
    session.query(MonthlyActivityEntry).filter_by(tenant_id=test_tenant_id).delete()
    session.query(ACPeriod).filter_by(tenant_id=test_tenant_id).delete()
    session.query(Member).filter_by(tenant_id=test_tenant_id).delete()
    session.commit()

    print("\n>>> ALL TESTS PASSED! MonthlyActivityEntry persistence and custom titles fully verified! <<<")

if __name__ == "__main__":
    test_monthly_activity_title_flow()
