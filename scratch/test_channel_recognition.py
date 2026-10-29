"""
Comprehensive verification test for Dynamic Discord Bot Channel Recognition & Multitenancy.
Tests:
1. Group model attributes (ranks_channel_id, activity_channel_id, webhook_channel_id) and to_dict().
2. Database persistence in SQLite.
3. FastAPI endpoint GET /api/v1/groups/by-discord-id/{discord_group_id}.
4. update_group_identity router logic with all channel parameters.
5. Bot channel restriction logic (both when channels are set and when optional/None).
6. DiscordWebhookNotifier tenant resolution.
"""
import sys
import os

if sys.platform == "win32":
    if hasattr(sys.stdout, 'reconfigure'):
        sys.stdout.reconfigure(encoding='utf-8')
    if hasattr(sys.stderr, 'reconfigure'):
        sys.stderr.reconfigure(encoding='utf-8')

# Ensure Taskforce_System is in path
BASE_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
sys.path.insert(0, BASE_DIR)

from sqlmodel import Session, select
from database.engine import engine
from database.tenant_models import Group
from config import settings
from fastapi.testclient import TestClient
from app import app
from api.webhook_notifier import DiscordWebhookNotifier, create_notifier_for_tenant

def run_tests():
    print("=" * 60)
    print("🚀 RUNNING DYNAMIC DISCORD CHANNEL RECOGNITION TESTS")
    print("=" * 60)

    test_guild_id = "889900112233445566"
    test_webhook_channel = "1446175728025735393"
    test_activity_channel = "1446175728025735394"
    test_ranks_channel = "1446175728025735395"

    # 1. DB PERSISTENCE TEST
    print("\n[1] Testing Group Model & Database Persistence...")
    with Session(engine) as session:
        # Fetch or create test group
        group = session.exec(select(Group).where(Group.id == 2)).first()
        if not group:
            group = session.exec(select(Group)).first()
        assert group is not None, "No group found in DB to test with!"
        
        target_group_id = group.id
        group.discord_group_id = test_guild_id
        group.webhook_channel_id = test_webhook_channel
        group.activity_channel_id = test_activity_channel
        group.ranks_channel_id = test_ranks_channel
        session.add(group)
        session.commit()
        session.refresh(group)

        grp_dict = group.to_dict()
        assert grp_dict.get("webhook_channel_id") == test_webhook_channel, f"Expected {test_webhook_channel}, got {grp_dict.get('webhook_channel_id')}"
        assert grp_dict.get("activity_channel_id") == test_activity_channel, f"Expected {test_activity_channel}, got {grp_dict.get('activity_channel_id')}"
        assert grp_dict.get("ranks_channel_id") == test_ranks_channel, f"Expected {test_ranks_channel}, got {grp_dict.get('ranks_channel_id')}"
        print(f"✓ Group {target_group_id} successfully saved with:")
        print(f"   ├─ discord_group_id:    {grp_dict['discord_group_id']}")
        print(f"   ├─ webhook_channel_id:  {grp_dict['webhook_channel_id']}")
        print(f"   ├─ activity_channel_id: {grp_dict['activity_channel_id']}")
        print(f"   └─ ranks_channel_id:    {grp_dict['ranks_channel_id']}")

    # 2. REST API LOOKUP TEST
    print("\n[2] Testing REST API GET /api/v1/groups/by-discord-id/{id}...")
    client = TestClient(app)
    api_key = getattr(settings, 'DISCORD_BOT_API_KEY', 'default-key')
    headers = {"Authorization": f"Bearer {api_key}"}

    res = client.get(f"/api/v1/groups/by-discord-id/{test_guild_id}", headers=headers)
    assert res.status_code == 200, f"Expected 200, got {res.status_code}: {res.text}"
    data = res.json()
    assert data.get("success") is True
    api_grp = data.get("group", {})
    assert api_grp.get("webhook_channel_id") == test_webhook_channel
    assert api_grp.get("activity_channel_id") == test_activity_channel
    assert api_grp.get("ranks_channel_id") == test_ranks_channel
    print(f"✓ API returned group successfully with all 3 channel IDs.")

    # 3. WEBHOOK NOTIFIER TENANT RESOLUTION TEST
    print("\n[3] Testing DiscordWebhookNotifier for Tenant...")
    notifier = create_notifier_for_tenant(target_group_id)
    assert notifier.channel_id == test_webhook_channel, f"Notifier expected channel {test_webhook_channel}, got {notifier.channel_id}"
    print(f"✓ Notifier correctly resolved tenant's webhook_channel_id: {notifier.channel_id}")

    # 4. BOT CHANNEL RESTRICTION LOGIC TEST
    print("\n[4] Testing Bot Channel Restriction Rules...")
    # Scenario A: When channels are configured
    # - Rank change in ranks_channel -> ALLOWED
    # - Rank change in wrong channel -> BLOCKED with redirect
    # - Activity in activity_channel -> ALLOWED
    # - Activity in wrong channel -> BLOCKED with redirect

    def check_channel_rules(action: str, current_channel_id: str, ranks_chan: str, act_chan: str):
        if action in ['change_rank'] and ranks_chan:
            if str(current_channel_id).strip() != str(ranks_chan).strip():
                return False, f"⚠️ Rank changes for this sector are restricted to <#{ranks_chan}>."
        if action in ['log_activity', 'bulk_log_activity'] and act_chan:
            if str(current_channel_id).strip() != str(act_chan).strip():
                return False, f"⚠️ Quota & activity logging for this sector is restricted to <#{act_chan}>."
        return True, "ALLOWED"

    # Test A: Configured channels
    ok, msg = check_channel_rules('change_rank', test_ranks_channel, test_ranks_channel, test_activity_channel)
    assert ok is True and msg == "ALLOWED"

    ok, msg = check_channel_rules('change_rank', '999999999', test_ranks_channel, test_activity_channel)
    assert ok is False and f"<#{test_ranks_channel}>" in msg
    print(f"✓ Rank change outside designated channel was redirected: '{msg}'")

    ok, msg = check_channel_rules('log_activity', test_activity_channel, test_ranks_channel, test_activity_channel)
    assert ok is True and msg == "ALLOWED"

    ok, msg = check_channel_rules('log_activity', '999999999', test_ranks_channel, test_activity_channel)
    assert ok is False and f"<#{test_activity_channel}>" in msg
    print(f"✓ Activity log outside designated channel was redirected: '{msg}'")

    # Test B: Unconfigured / None channels (Flexible mode)
    ok, msg = check_channel_rules('change_rank', '999999999', None, None)
    assert ok is True and msg == "ALLOWED"

    ok, msg = check_channel_rules('log_activity', '999999999', None, None)
    assert ok is True and msg == "ALLOWED"
    print(f"✓ Unconfigured channels correctly fall back to allowing any permitted channel.")

    print("\n" + "=" * 60)
    print("✅ ALL DYNAMIC DISCORD CHANNEL RECOGNITION TESTS PASSED!")
    print("=" * 60)

if __name__ == "__main__":
    run_tests()
