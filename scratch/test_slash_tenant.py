import asyncio
import os
import sys

# Ensure bot and taskforce_system can be imported
bot_path = r"c:\Users\emend\OneDrive\Documentos\TF_System\bot"
tf_path = r"c:\Users\emend\OneDrive\Documentos\TF_System\Taskforce_System"
sys.path.insert(0, bot_path)
sys.path.insert(0, tf_path)

from tf_api_client import TFSystemAPI

async def test_slash_tenant_logic():
    print("[1] Initializing TFSystemAPI...")
    # Read API key from settings or config
    from config import settings
    api_key = settings.DISCORD_BOT_API_KEY
    api = TFSystemAPI(api_url="http://127.0.0.1:5000/api/v1", api_key=api_key)

    print("\n[2] Testing get_status without guild_id (Default Tenant)...")
    status = await api.get_status()
    print("Status Result:", status.get('status'), "| Tenant:", status.get('tenant_id'), "| Group:", status.get('group', {}).get('name'))
    assert status.get('success') is True, "Failed to get status"

    print("\n[3] Testing get_group_by_discord_id with known Discord Guild ID (Delta Sector: 1446175728025735392)...")
    delta_guild_id = "1446175728025735392"
    grp_res = await api.get_group_by_discord_id(delta_guild_id)
    print("Group Query Result:", grp_res)
    assert grp_res.get('success') is True, "Expected success for registered guild ID"
    assert grp_res.get('group', {}).get('name') == "Delta Sector"

    print("\n[4] Testing get_status WITH guild_id header routing...")
    tenant_status = await api.get_status(guild_id=delta_guild_id)
    print("Tenant Status Result:", tenant_status.get('tenant_id'), "| Group:", tenant_status.get('group', {}).get('name'))
    assert tenant_status.get('tenant_id') == 2, f"Expected tenant 2, got {tenant_status.get('tenant_id')}"
    assert tenant_status.get('group', {}).get('name') == "Delta Sector"

    print("\n[5] Testing get_group_by_discord_id with unmapped guild ID...")
    fake_guild_id = "999999999999999999"
    unmapped = await api.get_group_by_discord_id(fake_guild_id)
    print("Unmapped Result:", unmapped.get('error'))
    assert unmapped.get('success') is False

    print("\n=== ALL TENANT VERIFICATION TESTS PASSED SUCCESSFULLY! ===")

if __name__ == '__main__':
    asyncio.run(test_slash_tenant_logic())
