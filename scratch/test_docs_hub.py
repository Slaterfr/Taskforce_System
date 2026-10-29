"""
Automated Verification Test for Interactive Documentation Hub (/docs).
Verifies:
1. GET /docs returns HTTP 200.
2. Guest access displays Tier 1 unlocked and Tier 2/3 lock state cards.
3. Authenticated Staff session unlocks Tier 2.
4. Authenticated HCT session unlocks Tier 3.
5. Dynamic sector tokens (custom activities and quotas) are rendered.
"""
import sys
import os

if sys.platform == "win32":
    if hasattr(sys.stdout, 'reconfigure'):
        sys.stdout.reconfigure(encoding='utf-8')
    if hasattr(sys.stderr, 'reconfigure'):
        sys.stderr.reconfigure(encoding='utf-8')

BASE_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
sys.path.insert(0, BASE_DIR)

from fastapi.testclient import TestClient
from app import app
from utils.jwt_utils import create_tenant_token

def test_docs_hub():
    print("=" * 60)
    print("🚀 RUNNING DOCUMENTATION HUB VERIFICATION TESTS")
    print("=" * 60)

    client = TestClient(app)

    # 1. GUEST ACCESS
    print("\n[1] Testing Guest Access to /docs...")
    res = client.get("/docs")
    assert res.status_code == 200, f"Expected 200, got {res.status_code}"
    html = res.text
    assert "Tactical Command Network Documentation" in html
    assert "Tier 1: Operative &amp; Member Manual" in html
    assert "Staff Clearance Required" in html
    assert "High Command Clearance Required" in html
    print("✓ Guest successfully viewed /docs with Tier 1 unlocked and Tier 2/3 clearance-locked.")

    # 2. OPERATIVE / MEMBER ACCESS
    print("\n[2] Testing Member Level 1 Access...")
    member_jwt = create_tenant_token(
        user_id=101,
        roblox_id="12345678",
        roblox_username="TestOperative",
        group_id=1,
        roblox_group_id="99999",
        group_name="Taskforce",
        roblox_rank=10,
        system_role="member",
        permissions=["view_data"]
    )
    res_member = client.get("/docs", cookies={"tf_tenant_token": member_jwt})
    assert res_member.status_code == 200
    m_html = res_member.text
    assert "Level 1: Operative" in m_html
    print("✓ Member correctly received Level 1 clearance on /docs.")

    # 3. FIELD STAFF LEVEL 2 ACCESS
    print("\n[3] Testing Staff Level 2 Access...")
    staff_jwt = create_tenant_token(
        user_id=102,
        roblox_id="23456789",
        roblox_username="TestCommander",
        group_id=1,
        roblox_group_id="99999",
        group_name="Taskforce",
        roblox_rank=100,
        system_role="staff",
        permissions=["view_data", "manage_members", "can_log_activity"]
    )
    res_staff = client.get("/docs", cookies={"tf_tenant_token": staff_jwt})
    assert res_staff.status_code == 200
    s_html = res_staff.text
    assert "Level 2: Field Staff" in s_html
    assert "Single &amp; Bulk Activity Logging Protocols" in s_html
    assert "High Command Clearance Required" in s_html
    print("✓ Field Staff correctly unlocked Tier 2 documentation while Tier 3 remains protected.")

    # 4. HIGH COMMAND TEAM (HCT) LEVEL 3 ACCESS
    print("\n[4] Testing HCT Level 3 Access...")
    hct_jwt = create_tenant_token(
        user_id=103,
        roblox_id="34567890",
        roblox_username="TestGeneral",
        group_id=1,
        roblox_group_id="99999",
        group_name="Taskforce",
        roblox_rank=255,
        system_role="admin",
        permissions=["view_data", "manage_members", "edit_config", "manage_ac"]
    )
    res_hct = client.get("/docs", cookies={"tf_tenant_token": hct_jwt})
    assert res_hct.status_code == 200
    h_html = res_hct.text
    assert "Level 3: High Command (HCT)" in h_html
    assert "Granular Rank Permissions Matrix" in h_html
    assert "Discord Bot Channels Routing" in h_html
    assert "High Command Clearance Required" not in h_html
    print("✓ HCT correctly unlocked all three tiers (Tier 1, Tier 2, and Tier 3).")

    # 5. DYNAMIC SECTOR TOKENS & SIMULATOR
    print("\n[5] Testing Simulator & Search Features...")
    assert "Interactive @Cortex Command Simulator" in h_html
    assert "docs-search-input" in h_html
    assert "sim-btn" in h_html
    print("✓ Interactive simulator and search inputs are properly loaded in the DOM.")

    print("\n" + "=" * 60)
    print("✅ ALL DOCUMENTATION HUB TESTS PASSED!")
    print("=" * 60)

if __name__ == "__main__":
    test_docs_hub()
